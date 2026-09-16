"""Tests for the runtime tool-call control ledger."""

import json
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import UniqueConstraint
from sqlmodel import SQLModel, select

from app.adapters.storage.memory import InMemoryStoragePort
from app.kernel.commons.errors import ConflictError, KernelError
from app.kernel.commons.time import utc_now
from app.kernel.ports.tools.interface import ToolResponse
from app.kernel.runtime.db.models.runs import RunArtifact, RunStep, RunStepToolCall
from app.kernel.runtime.runs.tool_call_projection import project_run_tool_calls
from app.kernel.runtime.runs.tool_calls import (
    RuntimeToolExecutionService,
    ToolExecutionCommand,
    summarize_parameters,
    summarize_tool_payload,
)
from app.kernel.runtime.runs.writer import TraceWriter


def test_run_step_tool_call_model_registers_runtime_table():
    import app.kernel.runtime.db.models  # noqa: F401

    assert "run_step_tool_calls" in SQLModel.metadata.tables
    assert "agent_tool_invocations" not in SQLModel.metadata.tables
    assert RunStepToolCall.__tablename__ == "run_step_tool_calls"


def test_run_step_tool_call_model_lives_with_run_models():
    server_root = Path(__file__).parents[2]

    assert RunStepToolCall.__module__ == "app.kernel.runtime.db.models.runs"
    assert not (server_root / "app/kernel/runtime/db/models/tool_calls.py").exists()


def test_run_step_tool_call_model_uses_explicit_run_step_identity():
    record = RunStepToolCall(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        run_id="run-1",
        run_step_id="step-1",
        tool_call_id="call-1",
        idempotency_key="tool:run-1:call-1",
        request_hash="hash-1",
        tool_ref="tool:test:lookup",
    )

    assert record.id.startswith("rstc_")
    assert record.status == "claimed"
    assert record.attempt_count == 1
    assert record.parameters_summary_json == {}
    assert record.result_json == {}


def test_run_step_tool_call_model_enforces_scope_uniqueness_contracts():
    constraints = {
        constraint.name
        for constraint in RunStepToolCall.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert constraints == {
        "uq_run_step_tool_calls_scope_step",
        "uq_run_step_tool_calls_scope_run_call",
        "uq_run_step_tool_calls_scope_idempotency",
    }


@pytest.mark.asyncio
async def test_tool_call_projection_rejects_tool_step_without_control_record(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run(mode="agent", kind="agent")
    step = await writer.create_step(
        run.id,
        step_id="legacy-tool-step",
        step_type="tool",
    )

    with pytest.raises(KernelError, match="missing a run_step_tool_calls record"):
        await project_run_tool_calls(
            db=async_db,
            ctx=ctx,
            run_id=run.id,
            steps=[step],
            response_id="resp-contract",
        )


@pytest.mark.asyncio
async def test_tool_call_projection_rejects_control_record_without_run_step(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run(mode="agent", kind="agent")
    async_db.add(
        RunStepToolCall(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            run_id=run.id,
            run_step_id="missing-step",
            tool_call_id="call-orphan",
            idempotency_key=f"tool:{run.id}:call-orphan",
            request_hash="hash-orphan",
            tool_ref="tool:test:orphan",
        )
    )
    await async_db.commit()

    with pytest.raises(KernelError, match="references a missing run step"):
        await project_run_tool_calls(
            db=async_db,
            ctx=ctx,
            run_id=run.id,
            steps=[],
            response_id="resp-contract",
        )


def test_tool_parameter_summary_redacts_common_nested_credential_names():
    summary = summarize_parameters(
        {
            "headers": {
                "Authorization": "Bearer secret",
                "X-API-Key": "api-secret",
                "Cookie": "session=secret",
            },
            "credentials": {
                "access_token": "access-secret",
                "refresh-token": "refresh-secret",
                "clientSecret": "client-secret",
                "private_key": "private-secret",
            },
            "query": "safe",
        }
    )

    assert summary == {
        "headers": {
            "Authorization": "[REDACTED]",
            "X-API-Key": "[REDACTED]",
            "Cookie": "[REDACTED]",
        },
        "credentials": {
            "access_token": "[REDACTED]",
            "refresh-token": "[REDACTED]",
            "clientSecret": "[REDACTED]",
            "private_key": "[REDACTED]",
        },
        "query": "safe",
    }


def test_tool_payload_summary_redacts_and_bounds_result_payloads():
    summary = summarize_tool_payload(
        {
            "password": "result-secret",
            "content": "x" * 9000,
        }
    )

    assert summary["truncated"] is True
    assert summary["size_bytes"] > 8192
    assert "payload_hash" in summary
    assert "result-secret" not in json.dumps(summary)


def _service(db, ctx, writer, *, lease_owner: str, **kwargs) -> RuntimeToolExecutionService:
    return RuntimeToolExecutionService(
        db=db,
        ctx=ctx,
        trace_writer=writer,
        lease_owner=lease_owner,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_runtime_tool_execution_claim_creates_one_tool_step_and_redacted_record(
    async_db, ctx
):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run(mode="agent", kind="agent")
    service = _service(async_db, ctx, writer, lease_owner="worker-1")

    claim = await service.claim(
        ToolExecutionCommand(
            run_id=run.id,
            tool_call_id="call-1",
            tool_ref="tool:test:lookup",
            arguments={"query": "SOIT", "api_key": "must-not-persist"},
            idempotency_key=f"tool:{run.id}:call-1",
        )
    )

    assert claim.replayed is False
    assert claim.record.run_step_id == claim.run_step.id
    assert claim.run_step.step_type == "tool"
    assert claim.run_step.status == "preparing"
    assert claim.record.parameters_summary_json == {
        "query": "SOIT",
        "api_key": "[REDACTED]",
    }


@pytest.mark.asyncio
async def test_runtime_tool_execution_replays_completed_call_without_new_step(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run(mode="agent", kind="agent")
    service = _service(async_db, ctx, writer, lease_owner="worker-1")
    command = ToolExecutionCommand(
        run_id=run.id,
        tool_call_id="call-1",
        tool_ref="tool:test:lookup",
        arguments={"query": "SOIT"},
        idempotency_key=f"tool:{run.id}:call-1",
    )
    claim = await service.claim(command)
    await service.mark_running(claim.record.id)
    await service.complete(
        claim.record.id,
        ToolResponse(result={"answer": "governed runtime"}, metadata={"provider": "test"}),
    )

    replay = await service.claim(command)

    assert replay.replayed is True
    assert replay.cached_response is not None
    assert replay.cached_response.result == {"answer": "governed runtime"}
    assert replay.cached_response.metadata["idempotent_replay"] is True
    assert len((await async_db.exec(select(RunStepToolCall))).all()) == 1
    tool_steps = (await async_db.exec(select(RunStep).where(RunStep.step_type == "tool"))).all()
    assert len(tool_steps) == 1


@pytest.mark.asyncio
async def test_runtime_tool_execution_reclaims_expired_pre_outbound_claim(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run(mode="agent", kind="agent")
    command = ToolExecutionCommand(
        run_id=run.id,
        tool_call_id="call-1",
        tool_ref="tool:test:lookup",
        arguments={"query": "SOIT"},
        idempotency_key=f"tool:{run.id}:call-1",
    )
    first_service = _service(async_db, ctx, writer, lease_owner="worker-1")
    first = await first_service.claim(command)
    first.record.lease_expires_at = utc_now() - timedelta(seconds=1)
    async_db.add(first.record)
    await async_db.commit()

    reclaimed = await _service(async_db, ctx, writer, lease_owner="worker-2").claim(command)

    assert reclaimed.record.id == first.record.id
    assert reclaimed.record.run_step_id == first.run_step.id
    assert reclaimed.record.attempt_count == 2
    assert reclaimed.record.lease_owner == "worker-2"
    assert reclaimed.replayed is False


@pytest.mark.asyncio
async def test_runtime_tool_execution_marks_expired_outbound_call_in_doubt(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run(mode="agent", kind="agent")
    command = ToolExecutionCommand(
        run_id=run.id,
        tool_call_id="call-1",
        tool_ref="tool:test:write",
        arguments={"value": "one"},
        idempotency_key=f"tool:{run.id}:call-1",
    )
    first_service = _service(async_db, ctx, writer, lease_owner="worker-1")
    first = await first_service.claim(command)
    await first_service.mark_running(first.record.id)
    first.record.lease_expires_at = utc_now() - timedelta(seconds=1)
    async_db.add(first.record)
    await async_db.commit()

    with pytest.raises(ConflictError, match="outcome is in doubt"):
        await _service(async_db, ctx, writer, lease_owner="worker-2").claim(command)

    await async_db.refresh(first.record)
    await async_db.refresh(first.run_step)
    assert first.record.status == "in_doubt"
    assert first.run_step.status == "paused"


@pytest.mark.asyncio
async def test_runtime_tool_execution_stores_large_result_as_artifact(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run(mode="agent", kind="agent")
    storage = InMemoryStoragePort()
    service = _service(async_db, ctx, writer, lease_owner="worker-1", storage_port=storage)
    command = ToolExecutionCommand(
        run_id=run.id,
        tool_call_id="call-large",
        tool_ref="tool:test:large",
        arguments={},
        idempotency_key=f"tool:{run.id}:call-large",
    )
    claim = await service.claim(command)
    await service.mark_running(claim.record.id)

    await service.complete(claim.record.id, ToolResponse(result={"text": "x" * 9000}))

    await async_db.refresh(claim.record)
    assert claim.record.result_artifact_id is not None
    assert "text" not in json.dumps(claim.record.result_json)
    artifact = await async_db.get(RunArtifact, claim.record.result_artifact_id)
    assert artifact is not None
    assert artifact.step_id == claim.run_step.id
    replay = await service.claim(command)
    cached = await service.load_cached_response(replay)
    assert cached is not None
    assert cached.result == {"text": "x" * 9000}
    assert cached.metadata["idempotent_replay"] is True


@pytest.mark.asyncio
async def test_runtime_tool_execution_resumes_the_same_record_after_approval(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run(mode="agent", kind="agent")
    service = _service(async_db, ctx, writer, lease_owner="worker-1")
    command = ToolExecutionCommand(
        run_id=run.id,
        tool_call_id="call-approval",
        tool_ref="tool:test:write",
        arguments={"value": "original"},
        idempotency_key=f"tool:{run.id}:call-approval",
    )

    waiting = await service.prepare_waiting_approval(command)
    resumed = await service.claim(
        ToolExecutionCommand(
            **{
                **command.__dict__,
                "arguments": {"value": "approved-edit"},
                "resume_approval": True,
            }
        )
    )

    assert waiting.record.id == resumed.record.id
    assert waiting.run_step.id == resumed.run_step.id
    assert resumed.record.status == "claimed"
    assert resumed.record.attempt_count == 1
    assert resumed.record.parameters_summary_json == {"value": "approved-edit"}
    assert resumed.run_step.status == "waiting_approval"


@pytest.mark.asyncio
async def test_runtime_tool_execution_rejects_waiting_approval_without_outbound_call(
    async_db, ctx
):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run(mode="agent", kind="agent")
    service = _service(async_db, ctx, writer, lease_owner="worker-1")
    command = ToolExecutionCommand(
        run_id=run.id,
        tool_call_id="call-rejected",
        tool_ref="tool:test:write",
        arguments={"value": "blocked"},
        idempotency_key=f"tool:{run.id}:call-rejected",
    )
    waiting = await service.prepare_waiting_approval(command)

    rejected = await service.reject_approval(
        ToolExecutionCommand(
            **{
                **command.__dict__,
                "arguments": {"value": "edited-but-rejected"},
            }
        )
    )

    assert rejected.record.id == waiting.record.id
    assert rejected.record.status == "rejected"
    assert rejected.record.outbound_started_at is None
    assert rejected.record.parameters_summary_json == {"value": "blocked"}
    assert rejected.run_step.status == "canceled"


@pytest.mark.asyncio
async def test_runtime_tool_execution_retries_only_when_explicitly_allowed(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run(mode="agent", kind="agent")
    service = _service(async_db, ctx, writer, lease_owner="worker-1")
    command = ToolExecutionCommand(
        run_id=run.id,
        tool_call_id="call-retry",
        tool_ref="tool:test:read",
        arguments={"value": "one"},
        idempotency_key=f"tool:{run.id}:call-retry",
    )
    first = await service.claim(command)
    await service.mark_running(first.record.id)
    await service.complete(
        first.record.id,
        ToolResponse(result=None, success=False, error="temporary failure"),
    )

    cached_failure = await service.claim(command)
    retried = await service.claim(
        ToolExecutionCommand(**{**command.__dict__, "retry_failed": True})
    )

    assert cached_failure.replayed is True
    assert cached_failure.cached_response is not None
    assert cached_failure.cached_response.success is False
    assert retried.replayed is False
    assert retried.record.id == first.record.id
    assert retried.record.status == "claimed"
    assert retried.record.attempt_count == 2
    assert retried.record.outbound_started_at is None
    assert retried.run_step.status == "retrying"


@pytest.mark.asyncio
async def test_runtime_tool_execution_renews_only_the_current_workers_lease(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run(mode="agent", kind="agent")
    service = _service(async_db, ctx, writer, lease_owner="worker-1", lease_seconds=120)
    claim = await service.claim(
        ToolExecutionCommand(
            run_id=run.id,
            tool_call_id="call-lease",
            tool_ref="tool:test:slow",
            arguments={},
            idempotency_key=f"tool:{run.id}:call-lease",
        )
    )
    previous_expiry = claim.record.lease_expires_at

    renewed = await service.renew_lease(claim.record.id)

    assert previous_expiry is not None
    assert renewed.lease_expires_at is not None
    assert renewed.lease_expires_at >= previous_expiry
    with pytest.raises(ConflictError, match="lease owner"):
        await _service(async_db, ctx, writer, lease_owner="worker-2").renew_lease(
            claim.record.id
        )


@pytest.mark.asyncio
async def test_runtime_tool_execution_rejects_terminal_write_after_lease_is_lost(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run(mode="agent", kind="agent")
    service = _service(async_db, ctx, writer, lease_owner="worker-1")
    claim = await service.claim(
        ToolExecutionCommand(
            run_id=run.id,
            tool_call_id="call-owner",
            tool_ref="tool:test:write",
            arguments={"value": "one"},
            idempotency_key=f"tool:{run.id}:call-owner",
        )
    )
    await service.mark_running(claim.record.id)
    claim.record.lease_owner = "worker-2"
    async_db.add(claim.record)
    await async_db.commit()

    with pytest.raises(ConflictError, match="lease owner"):
        await service.complete(
            claim.record.id,
            ToolResponse(result={"ok": True}, success=True),
        )
