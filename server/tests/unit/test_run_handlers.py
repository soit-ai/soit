"""test_run_handlers

Tests for run handlers CSV export.
"""

import inspect
from decimal import Decimal

import pytest

from app.api.v1.run.handlers import RunHandlers
from app.kernel.commons.errors import KernelError
from app.kernel.commons.ids import generate_run_id
from app.kernel.commons.time import utc_now
from app.kernel.ports.common.audit import log_gateway_request
from app.kernel.runtime.db.models.responses import Response, ResponseEvent
from app.kernel.runtime.db.models.runs import Run, RunCostEntry, RunStepToolCall
from app.kernel.runtime.runs.service import RunService
from app.kernel.runtime.runs.writer import TraceWriter


def _persist_tool_call_ledger(db, ctx, step) -> RunStepToolCall:
    metrics = step.metrics_json if isinstance(step.metrics_json, dict) else {}
    tool_call = metrics.get("tool_call") if isinstance(metrics.get("tool_call"), dict) else {}
    raw_result = tool_call.get("result")
    result_json = (
        raw_result
        if isinstance(raw_result, dict) and "result" in raw_result
        else {"result": raw_result}
    )
    record = RunStepToolCall(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id=step.run_id,
        run_step_id=step.id,
        tool_call_id=f"call:{step.id}",
        idempotency_key=f"tool:{step.run_id}:{step.id}",
        request_hash=f"test:{step.id}",
        tool_ref=str(tool_call.get("tool_ref") or tool_call.get("tool_name")),
        status="succeeded",
        parameters_summary_json=dict(tool_call.get("arguments") or {}),
        result_json=result_json,
        created_by=ctx.user_id,
        outbound_started_at=step.started_at,
        completed_at=step.ended_at or utc_now(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@pytest.mark.asyncio
async def test_export_runs_csv_returns_rows(db, ctx):
    """CSV export includes header and run row."""
    run = Run(
        id=generate_run_id(),
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        trace_id="trace_csv",
        mode="chat",
        kind="chat",
        subject_kind="thread",
        subject_id="thr_chat",
        subject_version_id="app_v1",
        status="succeeded",
        started_at=utc_now(),
    )
    db.add(run)
    db.commit()

    service = RunService(db, ctx)
    handlers = RunHandlers(service)

    csv_text = await handlers.export_runs_csv(ctx, limit=10)
    lines = [line for line in csv_text.splitlines() if line.strip()]

    assert lines[0].startswith("run_id,mode,kind,status")
    assert run.id in lines[1]


def test_run_handlers_do_not_expose_workflow_id_alias():
    """Run handlers use subject filters only."""
    assert "workflow_id" not in inspect.signature(RunHandlers.list_runs).parameters
    assert "workflow_id" not in inspect.signature(RunHandlers.summarize_costs).parameters
    assert "workflow_id" not in inspect.signature(RunHandlers.export_runs_csv).parameters


@pytest.mark.asyncio
async def test_list_runs_filters_by_subject_scope(db, ctx):
    """Subject scope filters workflow runs."""
    run = Run(
        id=generate_run_id(),
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        trace_id="trace_workflow",
        mode="workflow",
        kind="workflow",
        subject_kind="workflow",
        subject_id="wf_workflow",
        subject_version_id="app_v1",
        status="succeeded",
        started_at=utc_now(),
    )
    db.add(run)
    db.commit()

    service = RunService(db, ctx)
    handlers = RunHandlers(service)

    response = await handlers.list_runs(ctx, subject_kind="workflow", subject_id="wf_workflow", page_size=10)
    assert response.items
    assert response.items[0].id == run.id


@pytest.mark.asyncio
async def test_list_runs_can_include_observe_summary(db, ctx):
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agent_observe_summary",
        subject_version_id="agent_v1",
    )
    child = trace_writer.create_run(
        mode="workflow",
        kind="workflow",
        subject_kind="workflow",
        subject_id="workflow_observe_summary",
        subject_version_id="workflow_v1",
    )
    step = trace_writer.create_step(run_id=run.id, step_type="tool", step_id="call_workflow")
    trace_writer.update_step_status(step.id, "running")
    trace_writer.update_step_status(
        step.id,
        "succeeded",
        metrics={
            "tool_call": {
                "tool_name": "wf:observe-summary",
                "tool_type": "workflow",
                "result": {"workflow_run_id": child.id},
            }
        },
    )
    await log_gateway_request(
        trace_writer=trace_writer,
        run_id=run.id,
        step_id=step.id,
        gateway_type="tool",
        request_data={"tool_ref": "wf:observe-summary"},
        response_data={"success": True},
    )
    db.add(
        RunCostEntry(
            run_id=run.id,
            step_id=step.id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            amount=Decimal("0.25"),
            unit="tokens",
            quantity=Decimal("25"),
            total_tokens=25,
        )
    )
    response = Response(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id=run.id,
        model="model:test",
        status="completed",
        input_json={},
        output_json={"text": "ok", "citations": [{"chunk_id": "chunk_observe"}]},
        usage_json={},
        metadata_json={},
    )
    db.add(response)
    db.commit()
    db.refresh(response)
    db.add(
        ResponseEvent(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            response_id=response.id,
            run_id=run.id,
            sequence=1,
            type="response.succeeded",
            source="agent",
            payload_json={"status": "succeeded"},
        )
    )
    db.commit()

    result = await RunHandlers(RunService(db, ctx)).list_runs(
        ctx,
        include_observe_summary=True,
        page_size=10,
    )

    item = next(item for item in result.items if item.id == run.id)
    assert item.observe_summary is not None
    assert item.observe_summary.model_dump() == {
        "step_count": 1,
        "tool_call_count": 1,
        "child_run_count": 1,
        "response_event_count": 1,
        "citation_count": 1,
        "audit_count": 1,
        "cost_entry_count": 1,
    }


@pytest.mark.asyncio
async def test_list_runs_filters_by_observe_summary_flags(db, ctx):
    trace_writer = TraceWriter(db, ctx)
    tool_run = trace_writer.create_run(mode="agent", subject_kind="agent", subject_id="agent_tool")
    citation_run = trace_writer.create_run(mode="agent", subject_kind="agent", subject_id="agent_citation")
    audit_run = trace_writer.create_run(mode="agent", subject_kind="agent", subject_id="agent_audit")
    step = trace_writer.create_step(run_id=tool_run.id, step_type="tool", step_id="call_tool")
    trace_writer.update_step_status(step.id, "running")
    trace_writer.update_step_status(step.id, "succeeded", metrics={"tool_call": {"tool_name": "tool.demo"}})
    audit_step = trace_writer.create_step(run_id=audit_run.id, step_type="llm", step_id="audit_llm")
    await log_gateway_request(
        trace_writer=trace_writer,
        run_id=audit_run.id,
        step_id=audit_step.id,
        gateway_type="tool",
        request_data={"tool_ref": "tool.audit"},
        response_data={"success": True},
    )
    db.add(
        Response(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            run_id=citation_run.id,
            model="model:test",
            status="completed",
            input_json={},
            output_json={"text": "ok", "citations": [{"chunk_id": "chunk_filter"}]},
            usage_json={},
            metadata_json={},
        )
    )
    db.commit()

    handlers = RunHandlers(RunService(db, ctx))
    tool_result = await handlers.list_runs(ctx, has_tool_call=True, page_size=10)
    citation_result = await handlers.list_runs(ctx, has_citation=True, page_size=10)
    audit_result = await handlers.list_runs(ctx, has_audit=True, page_size=10)

    assert [item.id for item in tool_result.items] == [tool_run.id]
    assert [item.id for item in citation_result.items] == [citation_run.id]
    assert [item.id for item in audit_result.items] == [audit_run.id]


@pytest.mark.asyncio
async def test_list_audits_returns_entries(db, ctx):
    """Audit entries can be queried by run_id."""
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="tool",
        subject_kind="tool",
        subject_id="tool_runtime",
        subject_version_id="app_v1",
    )
    step = trace_writer.create_step(run_id=run.id, step_type="tool", step_id="step_audit")

    await log_gateway_request(
        trace_writer=trace_writer,
        run_id=run.id,
        step_id=step.id,
        gateway_type="tool",
        request_data={"headers": {"authorization": "Bearer secret"}},
        response_data={"success": True},
    )

    service = RunService(db, ctx)
    handlers = RunHandlers(service)
    response = await handlers.list_audits(ctx, run_id=run.id, page_size=10)

    assert response.items
    assert response.items[0].run_id == run.id


@pytest.mark.asyncio
async def test_list_audits_can_query_workspace_audits_without_run_id(db, ctx):
    """Audit explorer can query workspace audit entries across runs."""
    trace_writer = TraceWriter(db, ctx)
    tool_run = trace_writer.create_run(mode="agent", subject_kind="agent", subject_id="agent_audit_tool")
    llm_run = trace_writer.create_run(mode="agent", subject_kind="agent", subject_id="agent_audit_llm")
    tool_step = trace_writer.create_step(run_id=tool_run.id, step_type="tool", step_id="step_tool_audit")
    llm_step = trace_writer.create_step(run_id=llm_run.id, step_type="llm", step_id="step_llm_audit")

    await log_gateway_request(
        trace_writer=trace_writer,
        run_id=tool_run.id,
        step_id=tool_step.id,
        gateway_type="tool",
        request_data={"tool_ref": "tool:http:request"},
        response_data={"success": True},
    )
    await log_gateway_request(
        trace_writer=trace_writer,
        run_id=llm_run.id,
        step_id=llm_step.id,
        gateway_type="model",
        request_data={"model_ref": "model:test"},
        response_data={"success": True},
    )

    response = await RunHandlers(RunService(db, ctx)).list_audits(
        ctx,
        step_type="tool",
        gateway_type="tool",
        page_size=10,
    )

    assert [item.run_id for item in response.items] == [tool_run.id]
    assert response.items[0].gateway_type == "tool"
    assert response.items[0].step_type == "tool"


@pytest.mark.asyncio
async def test_get_run_returns_normalized_detail_contract(db, ctx):
    """Run detail includes normalized explainability arrays."""
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agent_enterprise",
        subject_version_id="agent_v1",
    )
    child = trace_writer.create_run(
        mode="workflow",
        kind="workflow",
        subject_kind="workflow",
        subject_id="wf_ticket_triage",
        subject_version_id="workflow_v1",
    )
    step = trace_writer.create_step(run_id=run.id, step_type="tool", step_id="step_ticket")
    trace_writer.update_step_status(step.id, "running")
    trace_writer.update_step_status(
        step.id,
        "succeeded",
        metrics={
            "tool_call": {
                "tool_name": "wf:wf_ticket_triage",
                "tool_ref": "wf:wf_ticket_triage",
                "tool_type": "workflow",
                "status": "completed",
                "arguments": {"customer_id": "cust-1"},
                "result": {
                    "result": {
                        "workflow_run_id": child.id,
                        "output": {"ticket_id": "TICKET-1"},
                    }
                },
                "metadata": {"source": "agent.workflow"},
            }
        },
    )
    _persist_tool_call_ledger(db, ctx, step)
    await log_gateway_request(
        trace_writer=trace_writer,
        run_id=run.id,
        step_id=step.id,
        gateway_type="tool",
        request_data={"tool_ref": "wf:wf_ticket_triage"},
        response_data={"success": True},
    )
    child_step = trace_writer.create_step(run_id=child.id, step_type="tool", step_id="step_ticket_child")
    await log_gateway_request(
        trace_writer=trace_writer,
        run_id=child.id,
        step_id=child_step.id,
        gateway_type="tool",
        request_data={"tool_ref": "builtin.ticket.create_review_ticket"},
        response_data={"success": True},
    )
    trace_writer.record_cost(
        run_id=run.id,
        step_id=step.id,
        unit="tokens",
        quantity=12,
        model_ref="model:test:agent",
        prompt_tokens=7,
        completion_tokens=5,
        total_tokens=12,
    )
    response = Response(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id=run.id,
        model="model:test:agent",
        status="completed",
        input_json={},
        output_json={
            "text": "Ticket created.",
            "citations": [
                {
                    "chunk_id": "chunk_1",
                    "document_id": "doc_1",
                    "knowledge_id": "knowledge_1",
                    "snippet": "Refund policy context.",
                }
            ],
        },
        usage_json={},
        metadata_json={},
    )
    db.add(response)
    db.commit()
    db.refresh(response)
    db.add(
        ResponseEvent(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            response_id=response.id,
            run_id=run.id,
            sequence=1,
            type="response.succeeded",
            source="agent",
            payload_json={"response_id": response.id, "status": "succeeded"},
        )
    )
    db.commit()

    detail = await RunHandlers(RunService(db, ctx)).get_run(ctx, run.id)
    payload = detail.model_dump()

    for key in ("costs", "response_events", "tool_calls", "citations", "audits", "child_runs"):
        assert key in payload
        assert isinstance(payload[key], list)
    assert "governance_evidence" in payload
    assert payload["costs"][0]["unit"] == "tokens"
    assert payload["response_events"][0]["type"] == "response.succeeded"
    assert payload["tool_calls"][0]["tool_name"] == "wf:wf_ticket_triage"
    assert payload["citations"][0]["chunk_id"] == "chunk_1"
    assert payload["audits"][0]["gateway_type"] == "tool"
    assert {audit["run_id"] for audit in payload["audits"]} == {run.id, child.id}
    assert payload["child_runs"][0]["id"] == child.id


@pytest.mark.asyncio
async def test_get_run_includes_governance_evidence_matrix(db, ctx):
    """Run detail exposes a machine-readable governance evidence matrix."""
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agent_governed",
        subject_version_id="agent_version_governed",
    )
    child = trace_writer.create_run(
        mode="workflow",
        kind="workflow",
        subject_kind="workflow",
        subject_id="workflow_ticket",
        subject_version_id="workflow_version_governed",
    )
    step = trace_writer.create_step(run_id=run.id, step_type="tool", step_id="step_governed_tool")
    trace_writer.update_step_status(step.id, "running")
    trace_writer.update_step_status(
        step.id,
        "succeeded",
        metrics={
            "permission_scope": {
                "resource_type": "agent",
                "resource_id": "agent_governed",
                "action": "run",
                "allowed": True,
            },
            "capability_binding": {
                "source": "published_version",
                "agent_version_id": "agent_version_governed",
                "tool_refs": ["builtin.ticket.create_review_ticket"],
            },
            "secret_refs": ["secret:ticket_api_key"],
            "egress": {
                "decision": "allow",
                "url": "https://tickets.example.com/reviews",
            },
            "tool_call": {
                "tool_name": "builtin.ticket.create_review_ticket",
                "tool_ref": "builtin.ticket.create_review_ticket",
                "tool_type": "builtin",
                "status": "completed",
                "arguments": {"customer_id": "cust-1"},
                "result": {"result": {"workflow_run_id": child.id}},
            },
        },
    )
    _persist_tool_call_ledger(db, ctx, step)
    await log_gateway_request(
        trace_writer=trace_writer,
        run_id=run.id,
        step_id=step.id,
        gateway_type="tool",
        request_data={
            "tool_ref": "builtin.ticket.create_review_ticket",
            "secret_refs": ["secret:ticket_api_key"],
            "egress": {"decision": "allow"},
        },
        response_data={"success": True},
    )
    trace_writer.record_cost(
        run_id=run.id,
        step_id=step.id,
        unit="tokens",
        quantity=20,
        model_ref="model:test:agent",
        prompt_tokens=8,
        completion_tokens=12,
        total_tokens=20,
    )
    response = Response(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id=run.id,
        model="model:test:agent",
        status="completed",
        input_json={},
        output_json={
            "text": "Ticket created.",
            "citations": [{"chunk_id": "chunk_policy", "knowledge_id": "knowledge_support"}],
        },
        usage_json={},
        metadata_json={},
    )
    db.add(response)
    db.commit()
    db.refresh(response)
    db.add(
        ResponseEvent(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            response_id=response.id,
            run_id=run.id,
            sequence=1,
            type="response.succeeded",
            source="agent",
            payload_json={"response_id": response.id},
        )
    )
    db.commit()

    detail = await RunHandlers(RunService(db, ctx)).get_run(ctx, run.id)
    evidence = {item["key"]: item for item in detail.model_dump()["governance_evidence"]}

    assert set(evidence) == {
        "actor_scope",
        "subject_version",
        "capability_binding",
        "permission_scope",
        "secret_boundary",
        "egress_policy",
        "audit_record",
        "cost_attribution",
        "trace_timeline",
        "tool_call",
        "knowledge_citation",
        "child_workflow",
        "replay_ready",
    }
    assert evidence["actor_scope"]["status"] == "pass"
    assert evidence["subject_version"]["status"] == "pass"
    assert evidence["capability_binding"]["status"] == "pass"
    assert evidence["permission_scope"]["status"] == "pass"
    assert evidence["secret_boundary"]["status"] == "pass"
    assert evidence["egress_policy"]["status"] == "pass"
    assert evidence["audit_record"]["status"] == "pass"
    assert evidence["cost_attribution"]["status"] == "pass"
    assert evidence["trace_timeline"]["status"] == "pass"
    assert evidence["tool_call"]["status"] == "pass"
    assert evidence["knowledge_citation"]["status"] == "pass"
    assert evidence["child_workflow"]["status"] == "pass"
    assert evidence["replay_ready"]["status"] == "pass"
    assert step.id in evidence["tool_call"]["evidence_refs"]
    assert "secret:ticket_api_key" in evidence["secret_boundary"]["evidence_refs"]


@pytest.mark.asyncio
async def test_governance_evidence_reports_missing_required_items(db, ctx):
    """Missing governance proof is explicit instead of silently empty."""
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agent_missing_governance",
        subject_version_id=None,
    )

    detail = await RunHandlers(RunService(db, ctx)).get_run(ctx, run.id)
    evidence = {item["key"]: item for item in detail.model_dump()["governance_evidence"]}

    assert evidence["actor_scope"]["status"] == "pass"
    assert evidence["subject_version"]["status"] == "fail"
    assert evidence["subject_version"]["missing"] == ["subject_version_id"]
    assert evidence["trace_timeline"]["status"] == "fail"
    assert evidence["cost_attribution"]["status"] == "not_applicable"
    assert evidence["knowledge_citation"]["status"] == "not_applicable"
    assert evidence["replay_ready"]["status"] == "fail"
    assert "steps" in evidence["replay_ready"]["missing"]


@pytest.mark.asyncio
async def test_governance_evidence_is_applicability_aware_for_direct_chat(db, ctx):
    """Optional agent governance surfaces do not fail a plain model response."""
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="response",
        kind="response",
        subject_kind="thread",
        subject_id="thread_direct_chat",
    )
    step = trace_writer.create_step(
        run_id=run.id,
        step_type="llm",
        step_id="step_direct_chat_llm",
    )
    trace_writer.update_step_status(step.id, "running")
    trace_writer.update_step_status(
        step.id,
        "succeeded",
        metrics={"model_ref": "model:openai-main:gpt-5.5"},
    )
    trace_writer.record_cost(
        run_id=run.id,
        step_id=step.id,
        unit="tokens",
        quantity=10,
        model_ref="model:openai-main:gpt-5.5",
        prompt_tokens=6,
        completion_tokens=4,
        total_tokens=10,
    )
    response = Response(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        thread_id="thread_direct_chat",
        run_id=run.id,
        model="model:openai-main:gpt-5.5",
        status="completed",
        input_json={},
        output_json={"text": "Hello."},
        usage_json={},
        metadata_json={},
    )
    db.add(response)
    db.commit()
    db.refresh(response)
    db.add(
        ResponseEvent(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            thread_id="thread_direct_chat",
            response_id=response.id,
            run_id=run.id,
            sequence=1,
            type="response.succeeded",
            source="responses",
            payload_json={"response_id": response.id},
        )
    )
    db.commit()

    detail = await RunHandlers(RunService(db, ctx)).get_run(ctx, run.id)
    evidence = {item["key"]: item for item in detail.model_dump()["governance_evidence"]}

    assert evidence["subject_version"]["status"] == "not_applicable"
    assert evidence["capability_binding"]["status"] == "not_applicable"
    assert evidence["permission_scope"]["status"] == "not_applicable"
    assert evidence["secret_boundary"]["status"] == "not_applicable"
    assert evidence["egress_policy"]["status"] == "not_applicable"
    assert evidence["audit_record"]["status"] == "not_applicable"
    assert evidence["cost_attribution"]["status"] == "pass"
    assert evidence["knowledge_citation"]["status"] == "not_applicable"
    assert evidence["replay_ready"]["status"] == "pass"


@pytest.mark.asyncio
async def test_governance_evidence_requires_proof_for_an_executed_tool(db, ctx):
    """A real tool call keeps its audit, secret, and egress proof requirements."""
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agent_tool_without_proof",
        subject_version_id="agent_version_tool_without_proof",
    )
    step = trace_writer.create_step(
        run_id=run.id,
        step_type="tool",
        step_id="step_tool_without_proof",
    )
    trace_writer.update_step_status(step.id, "running")
    trace_writer.update_step_status(
        step.id,
        "succeeded",
        metrics={
            "tool_call": {
                "tool_name": "external.ticket.create",
                "tool_ref": "external.ticket.create",
                "tool_type": "builtin",
                "status": "completed",
                "arguments": {},
                "result": {"created": True},
            }
        },
    )
    _persist_tool_call_ledger(db, ctx, step)

    detail = await RunHandlers(RunService(db, ctx)).get_run(ctx, run.id)
    evidence = {item["key"]: item for item in detail.model_dump()["governance_evidence"]}

    assert evidence["tool_call"]["status"] == "pass"
    assert evidence["audit_record"]["status"] == "fail"
    assert evidence["secret_boundary"]["status"] == "warning"
    assert evidence["egress_policy"]["status"] == "warning"
    assert "audits" in evidence["replay_ready"]["missing"]


@pytest.mark.asyncio
async def test_governance_evidence_fails_when_tool_step_has_no_call_ledger(db, ctx):
    """A tool step must not be treated as non-applicable when its ledger is missing."""

    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agent_tool_missing_ledger",
        subject_version_id="agent_version_tool_missing_ledger",
    )
    step = trace_writer.create_step(
        run_id=run.id,
        step_type="tool",
        step_id="step_tool_missing_ledger",
    )
    trace_writer.update_step_status(step.id, "running")
    trace_writer.update_step_status(step.id, "succeeded")

    with pytest.raises(KernelError, match="missing a run_step_tool_calls record"):
        await RunHandlers(RunService(db, ctx)).get_run(ctx, run.id)


