"""test_tool_secret_injection

Unit tests for tool secret injection and redaction.
"""

from datetime import UTC

import pytest
from sqlalchemy import select
from tenacity import RetryError

from app.adapters.tools.router import RegistryToolRouterPort
from app.kernel.commons.errors import ForbiddenError, ValidationError
from app.kernel.ports.secrets.interface import SecretsPort
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.ports.tools.policy import ToolPolicyGateway
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.db.models.runs import RunStep, RunStepToolCall
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.security import egress
from app.settings.settings import settings


class DummySecretsPort(SecretsPort):
    """Secrets port stub for tool policy tests."""

    async def get_secret(self, secret_ref: str, **kwargs):
        return "supersecret"

    async def set_secret(self, secret_ref: str, value: str, **kwargs):
        raise RuntimeError("Not implemented")

    async def delete_secret(self, secret_ref: str, **kwargs):
        raise RuntimeError("Not implemented")


class DummyToolPort(ToolPort):
    """Tool port stub capturing parameters."""

    def __init__(self):
        self.last_parameters = None

    async def invoke(self, tool_ref: str, parameters: dict, **kwargs):
        self.last_parameters = parameters
        return ToolResponse(result={"ok": True}, success=True, metadata={})


class FailingToolPort(ToolPort):
    """Tool port that fails after the governed claim is durable."""

    async def invoke(self, tool_ref: str, parameters: dict, **kwargs):
        raise RuntimeError("upstream response was lost")


class InspectingLeaseToolPort(ToolPort):
    """Tool port that observes the durable lease at the outbound boundary."""

    def __init__(self, db):
        self.db = db
        self.remaining_lease_seconds = 0.0

    async def invoke(self, tool_ref: str, parameters: dict, **kwargs):
        record_result = self.db.exec(
            select(RunStepToolCall).where(
                RunStepToolCall.tool_call_id == kwargs["tool_call_id"]
            )
        ).one()
        record = (
            record_result
            if isinstance(record_result, RunStepToolCall)
            else record_result[0]
        )
        expires_at = record.lease_expires_at
        assert expires_at is not None
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        from app.kernel.commons.time import utc_now

        self.remaining_lease_seconds = (expires_at - utc_now()).total_seconds()
        return ToolResponse(result={"ok": True}, success=True, metadata={})


class RetryableToolPort(ToolPort):
    """Return one durable failure followed by a success."""

    def __init__(self):
        self.call_count = 0

    async def invoke(self, tool_ref: str, parameters: dict, **kwargs):
        self.call_count += 1
        if self.call_count == 1:
            return ToolResponse(result=None, success=False, error="temporary failure")
        return ToolResponse(result={"ok": True}, success=True, metadata={})


def _disable_db_policy_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.infra.db.session as db_session

    monkeypatch.setattr(
        db_session,
        "get_db_sync",
        lambda: (_ for _ in ()).throw(RuntimeError("DB disabled in unit test")),
    )


def _audit_payload(audit_result) -> str:
    audit = audit_result if isinstance(audit_result, AuditEvent) else audit_result[0]
    return str(audit.payload_json)


@pytest.mark.asyncio
async def test_tool_policy_injects_and_redacts_secrets(db, ctx):
    """Secret refs are injected for execution and redacted in audit logs."""
    dummy_tool = DummyToolPort()
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="workflow",
        kind="workflow",
        subject_kind="workflow",
        subject_id="wf_secret",
        subject_version_id="ver_workflow",
    )

    gateway = ToolPolicyGateway(
        gateway=dummy_tool,
        ctx=ctx,
        trace_writer=trace_writer,
        secrets_port=DummySecretsPort(),
    )

    parameters = {
        "headers": {"Authorization": {"secret_ref": "secret:test_token"}},
        "query": {"token": {"secret_ref": "secret:test_token"}},
        "body": {"payload": {"secret_ref": "secret:test_token"}},
    }

    await gateway.invoke(
        tool_ref="tool:http:demo",
        parameters=parameters,
        run_id=run.id,
        tool_call_id="call-secret-redaction",
    )

    assert dummy_tool.last_parameters["headers"]["Authorization"] == "supersecret"
    assert dummy_tool.last_parameters["query"]["token"] == "supersecret"
    assert dummy_tool.last_parameters["body"]["payload"] == "supersecret"

    result = db.exec(select(RunStep).where(RunStep.run_id == run.id)).first()
    if result is None:
        raise AssertionError("Expected run step for tool invocation")
    if not isinstance(result, RunStep):
        if isinstance(result, list | tuple):
            result = result[0]
        elif hasattr(result, "_mapping"):
            result = result[0]
    step = result

    audit = db.exec(
        select(AuditEvent).where(
            AuditEvent.run_id == run.id,
            AuditEvent.step_id == step.id,
        )
    ).first()
    assert audit is not None
    audit_json = _audit_payload(audit)
    assert "supersecret" not in audit_json
    assert "secret:test_token" in audit_json
    call_record_result = db.exec(
        select(RunStepToolCall).where(
            RunStepToolCall.run_id == run.id,
            RunStepToolCall.tool_call_id == "call-secret-redaction",
        )
    ).one()
    call_record = (
        call_record_result
        if isinstance(call_record_result, RunStepToolCall)
        else call_record_result[0]
    )
    assert call_record.run_step_id == step.id
    assert "supersecret" not in str(call_record.parameters_summary_json)
    assert call_record.status == "succeeded"
    tool_call = (step.metrics_json or {}).get("tool_call")
    assert tool_call["tool_ref"] == "tool:http:demo"
    assert tool_call["status"] == "completed"
    assert tool_call["arguments"]["headers"]["Authorization"]["secret_ref"] == "secret:test_token"
    assert "supersecret" not in str(tool_call)

    response_service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=trace_writer,
    )
    response = response_service.create_linked_response(run_id=run.id)
    _, _, tool_calls = response_service.get_response_detail(response.id)
    assert len(tool_calls) == 1
    assert tool_calls[0]["tool_name"] == "tool:http:demo"
    assert tool_calls[0]["tool_call_id"] == "call-secret-redaction"
    assert tool_calls[0]["run_step_tool_call_id"] == call_record.id
    assert tool_calls[0]["attempt_count"] == 1
    assert tool_calls[0]["arguments_json"]["headers"]["Authorization"]["secret_ref"] == "secret:test_token"


@pytest.mark.asyncio
async def test_tool_policy_finishes_ledger_when_adapter_raises(db, ctx):
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(mode="workflow", kind="workflow")
    gateway = ToolPolicyGateway(
        gateway=FailingToolPort(),
        ctx=ctx,
        trace_writer=trace_writer,
        enable_egress_check=False,
    )

    with pytest.raises(RetryError):
        await gateway.invoke(
            tool_ref="tool:function:unstable",
            parameters={"value": "once"},
            run_id=run.id,
            tool_call_id="call-failed",
            idempotency_key=f"tool:{run.id}:call-failed",
        )

    record_result = db.exec(
        select(RunStepToolCall).where(RunStepToolCall.run_id == run.id)
    ).one()
    record = record_result if isinstance(record_result, RunStepToolCall) else record_result[0]
    step_result = db.exec(select(RunStep).where(RunStep.run_id == run.id)).one()
    step = step_result if isinstance(step_result, RunStep) else step_result[0]
    assert record.status == "failed"
    assert record.error_code == "TOOL_EXECUTION_FAILED"
    assert record.error_message == "Tool execution failed"
    assert step.status == "failed"


@pytest.mark.asyncio
async def test_tool_policy_lease_outlives_the_bounded_outbound_call(db, ctx):
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(mode="workflow", kind="workflow")
    tool_port = InspectingLeaseToolPort(db)
    gateway = ToolPolicyGateway(
        gateway=tool_port,
        ctx=ctx,
        trace_writer=trace_writer,
        enable_egress_check=False,
    )

    await gateway.invoke(
        tool_ref="tool:function:slow",
        parameters={},
        run_id=run.id,
        tool_call_id="call-slow",
        timeout_s=90,
    )

    assert tool_port.remaining_lease_seconds >= 95


@pytest.mark.asyncio
async def test_tool_policy_retries_a_failed_call_only_when_explicitly_requested(db, ctx):
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(mode="workflow", kind="workflow")
    tool_port = RetryableToolPort()
    gateway = ToolPolicyGateway(
        gateway=tool_port,
        ctx=ctx,
        trace_writer=trace_writer,
        enable_egress_check=False,
    )
    call_kwargs = {
        "run_id": run.id,
        "tool_call_id": "call-explicit-retry",
        "idempotency_key": f"tool:{run.id}:call-explicit-retry",
    }

    failed = await gateway.invoke(
        tool_ref="tool:function:retryable",
        parameters={"value": "one"},
        **call_kwargs,
    )
    replayed = await gateway.invoke(
        tool_ref="tool:function:retryable",
        parameters={"value": "one"},
        **call_kwargs,
    )
    succeeded = await gateway.invoke(
        tool_ref="tool:function:retryable",
        parameters={"value": "one"},
        retry_failed=True,
        **call_kwargs,
    )

    record_result = db.exec(
        select(RunStepToolCall).where(RunStepToolCall.run_id == run.id)
    ).one()
    record = record_result if isinstance(record_result, RunStepToolCall) else record_result[0]
    assert failed.success is False
    assert replayed.success is False
    assert replayed.metadata["idempotent_replay"] is True
    assert succeeded.success is True
    assert tool_port.call_count == 2
    assert record.status == "succeeded"
    assert record.attempt_count == 2
    assert len(db.exec(select(RunStep).where(RunStep.run_id == run.id)).all()) == 1


@pytest.mark.asyncio
async def test_tool_policy_audits_egress_denials(db, ctx, monkeypatch):
    """Blocked egress attempts are auditable even when the tool is never invoked."""
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["api.example.com"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    monkeypatch.setattr(egress, "_egress_policy", None)
    _disable_db_policy_lookup(monkeypatch)

    dummy_tool = DummyToolPort()
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="workflow",
        kind="workflow",
        subject_kind="workflow",
        subject_id="wf_egress",
        subject_version_id="ver_workflow",
    )
    gateway = ToolPolicyGateway(
        gateway=dummy_tool,
        ctx=ctx,
        trace_writer=trace_writer,
    )

    with pytest.raises(ForbiddenError):
        await gateway.invoke(
            tool_ref="tool:http:demo",
            parameters={"url": "https://evil.example/api"},
            run_id=run.id,
        )

    assert dummy_tool.last_parameters is None
    result = db.exec(select(RunStep).where(RunStep.run_id == run.id)).first()
    if result is None:
        raise AssertionError("Expected run step for blocked egress")
    if not isinstance(result, RunStep):
        if isinstance(result, list | tuple):
            result = result[0]
        elif hasattr(result, "_mapping"):
            result = result[0]
    step = result
    assert step.status == "failed"
    audit = db.exec(
        select(AuditEvent).where(
            AuditEvent.run_id == run.id,
            AuditEvent.step_id == step.id,
        )
    ).first()
    assert audit is not None
    audit_json = _audit_payload(audit)
    assert "https://evil.example/api" in audit_json
    assert "ForbiddenError" in audit_json
    tool_call = (step.metrics_json or {}).get("tool_call")
    assert tool_call["tool_ref"] == "tool:http:demo"
    assert tool_call["status"] == "failed"
    assert tool_call["arguments"]["url"] == "https://evil.example/api"


@pytest.mark.asyncio
async def test_builtin_ticket_tool_is_governed_and_redacts_secret(db, ctx, monkeypatch):
    """Ticket tool requires workspace context, applies egress, and audits redacted inputs."""
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["tickets.example.local"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    monkeypatch.setattr(egress, "_egress_policy", None)
    _disable_db_policy_lookup(monkeypatch)

    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="workflow",
        kind="workflow",
        subject_kind="workflow",
        subject_id="wf_ticket",
        subject_version_id="ver_ticket",
    )
    router = RegistryToolRouterPort()
    gateway = ToolPolicyGateway(
        gateway=router,
        ctx=ctx,
        trace_writer=trace_writer,
        secrets_port=DummySecretsPort(),
    )

    with pytest.raises(ValidationError):
        await router.invoke(
            "builtin.ticket.create_review_ticket",
            {"customer_id": "cust-1", "message": "refund request"},
            strict_registry=True,
        )

    response = await gateway.invoke(
        tool_ref="builtin.ticket.create_review_ticket",
        parameters={
            "url": "https://tickets.example.local/reviews",
            "customer_id": "cust-1",
            "priority": "high",
            "message": "Refund request for invoice 123",
            "api_token": {"secret_ref": "secret:ticket_api"},
        },
        strict_registry=True,
        ctx=ctx,
        run_id=run.id,
    )

    assert response.success is True
    assert response.result["ticket_id"] == "TICKET-A5EBADC2"
    assert response.result["status"] == "created"
    assert response.result["review_url"] == "https://tickets.example.local/reviews/TICKET-A5EBADC2"
    assert "supersecret" not in str(response.result)

    result = db.exec(select(RunStep).where(RunStep.run_id == run.id)).first()
    if result is None:
        raise AssertionError("Expected run step for ticket tool invocation")
    if not isinstance(result, RunStep):
        if isinstance(result, list | tuple):
            result = result[0]
        elif hasattr(result, "_mapping"):
            result = result[0]
    step = result
    assert step.status == "succeeded"
    audit = db.exec(
        select(AuditEvent).where(
            AuditEvent.run_id == run.id,
            AuditEvent.step_id == step.id,
        )
    ).first()
    assert audit is not None
    audit_json = _audit_payload(audit)
    assert "supersecret" not in audit_json
    assert "secret:ticket_api" in audit_json
    tool_call = (step.metrics_json or {}).get("tool_call")
    assert tool_call["tool_ref"] == "builtin.ticket.create_review_ticket"
    assert tool_call["status"] == "completed"
    assert tool_call["arguments"]["api_token"]["secret_ref"] == "secret:ticket_api"
    assert "supersecret" not in str(tool_call)


