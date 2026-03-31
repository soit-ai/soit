"""Entrypoint tests for the observability workspace dashboard API."""

from decimal import Decimal

from fastapi import status

from app.kernel.trace.models import Run, RunCostEntry, RunStep


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def test_observability_dashboard_returns_workspace_summary(client, db):
    run = Run(
        id="run_dashboard_observability",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="test-user",
        trace_id="trace_dashboard_observability",
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agt_dashboard",
        subject_version_id="agtv_dashboard",
        status="failed",
        input_summary="hello",
        output_summary="world",
        duration_ms=120,
    )
    step = RunStep(
        id="step_dashboard_observability",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        trace_id="trace_dashboard_observability",
        run_id=run.id,
        step_id="tool:filesystem:read_file",
        step_type="tool",
        node_id="workflow-node-1",
        status="failed",
        metrics_json={"latency_ms": 120},
        error_message="boom",
    )
    cost = RunCostEntry(
        run_id=run.id,
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        amount=Decimal("0.25"),
        unit="tokens",
        quantity=Decimal("100"),
        provider="openai",
        model_ref="model:openai:gpt-5.1",
        tool_ref="mcp_tool:filesystem:read_file",
        prompt_tokens=60,
        completion_tokens=40,
        total_tokens=100,
    )
    db.add(run)
    db.add(step)
    db.add(cost)
    db.commit()

    resp = client.get("/api/v1/observability/dashboard", headers=_headers())
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert "workspace_summary" in data
    assert "agent_summaries" in data
    assert "model_costs" in data
    assert "workflow_bottlenecks" in data
    assert "tool_health" in data
    assert "knowledge_quality" in data
    assert "approvals_summary" in data
