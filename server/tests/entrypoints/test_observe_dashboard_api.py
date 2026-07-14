"""Entrypoint tests for the observe workspace dashboard API."""

from datetime import timedelta
from decimal import Decimal

from fastapi import status

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.common.audit import log_gateway_request
from app.kernel.runtime.db.models.responses import Response, ResponseEvent
from app.kernel.runtime.db.models.runs import Run, RunCostEntry, RunStep
from app.kernel.runtime.runs.writer import TraceWriter


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def _test_ctx() -> RequestContext:
    return RequestContext(
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="test-user",
        tenant_role="Owner",
        workspace_role="Owner",
    )


def test_observe_dashboard_returns_workspace_summary(client, db):
    run = Run(
        id="run_dashboard_observe",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="test-user",
        trace_id="trace_dashboard_observe",
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agt_dashboard",
        subject_version_id="agtv_dashboard",
        status="failed",
        input_summary="hello",
        output_summary="world",
        duration_ms=120,
        error_message="tool call failed",
    )
    step = RunStep(
        id="step_dashboard_observe",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        trace_id="trace_dashboard_observe",
        run_id=run.id,
        step_id="step_generated_tool_call",
        step_type="tool",
        node_id="workflow-node-1",
        status="failed",
        metrics_json={
            "latency_ms": 120,
            "tool_call": {
                "tool_ref": "mcp_tool:filesystem:read_file",
                "tool_name": "mcp_tool:filesystem:read_file",
                "status": "failed",
            },
        },
        error_message="boom",
    )
    retrieval_step = RunStep(
        id="step_dashboard_retrieval",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        trace_id="trace_dashboard_observe",
        run_id=run.id,
        step_id="retrieve",
        step_type="retrieval",
        status="succeeded",
        metrics_json={
            "knowledge_id": "knowledge:kb_support",
            "strategy": "hybrid",
            "result_count": 3,
            "citation_count": 2,
            "avg_score": 0.75,
        },
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
    db.add(retrieval_step)
    db.add(cost)
    db.commit()

    resp = client.get("/api/v1/observe/dashboard", headers=_headers())
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert "workspace_summary" in data
    assert "agent_summaries" in data
    assert "model_costs" in data
    assert "workflow_bottlenecks" in data
    assert "tool_health" in data
    assert "knowledge_quality" in data
    assert "approvals_summary" in data
    assert data["recent_runs"][0]["run_id"] == run.id
    assert data["recent_runs"][0]["status"] == "failed"
    assert data["recent_runs"][0]["cost_usd"] == 0.25
    assert data["recent_runs"][0]["failure_reason"] == "tool call failed"
    assert data["recent_runs"][0]["detail_url"] == f"/observe/runs/{run.id}"
    assert data["metric_cards"][0]["run_id"] == run.id
    assert data["metric_cards"][0]["detail_url"] == f"/observe/runs/{run.id}"
    assert data["section"]["rows"][0]["latest_run_id"] == run.id
    assert data["section"]["rows"][0]["detail_url"] == f"/observe/runs/{run.id}"
    assert data["tool_health"] == [
        {
            "tool_ref": "mcp_tool:filesystem:read_file",
            "call_count": 1,
            "failed_call_count": 1,
            "failure_rate": 1.0,
            "health_status": "critical",
        }
    ]
    assert data["knowledge_quality"] == [
        {
            "knowledge_id": "knowledge:kb_support",
            "query_count": 1,
            "failed_query_count": 0,
            "result_count": 3,
            "citation_count": 2,
            "avg_score": 0.75,
            "failure_rate": 0.0,
            "avg_results_per_query": 3.0,
            "citation_rate": 0.6667,
            "quality_status": "healthy",
        }
    ]


def test_observe_dashboard_default_range_includes_last_24h(client, db):
    now = utc_now()
    run = Run(
        id="run_dashboard_default_24h",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="test-user",
        trace_id="trace_dashboard_default_24h",
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agent:recent-demo",
        subject_version_id="agtv_recent_demo",
        status="succeeded",
        started_at=now - timedelta(minutes=90),
        ended_at=now - timedelta(minutes=89),
        duration_ms=60_000,
    )
    db.add(run)
    db.commit()

    default_resp = client.get("/api/v1/observe/dashboard", headers=_headers())
    assert default_resp.status_code == status.HTTP_200_OK
    default_data = default_resp.json()["data"]
    assert [item["run_id"] for item in default_data["recent_runs"]] == [run.id]

    one_hour_resp = client.get(
        "/api/v1/observe/dashboard",
        params={"range": "1h"},
        headers=_headers(),
    )
    assert one_hour_resp.status_code == status.HTTP_200_OK
    one_hour_data = one_hour_resp.json()["data"]
    assert one_hour_data["recent_runs"] == []


def test_observe_dashboard_recent_runs_include_observe_summary(client, db):
    now = utc_now()
    trace_writer = TraceWriter(db, _test_ctx())
    parent = trace_writer.create_run(
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agent:enterprise",
        subject_version_id="agtv_enterprise",
        run_id="run_dashboard_summary_parent",
    )
    child = trace_writer.create_run(
        mode="workflow",
        kind="workflow",
        subject_kind="workflow",
        subject_id="workflow:ticket-triage",
        subject_version_id="wfv_ticket",
        run_id="run_dashboard_summary_child",
    )
    parent.started_at = now
    child.started_at = now
    step = trace_writer.create_step(run_id=parent.id, step_type="tool", step_id="call_ticket_workflow")
    trace_writer.update_step_status(
        step.id,
        "succeeded",
        metrics={
            "tool_call": {
                "tool_name": "wf:ticket-triage",
                "tool_ref": "wf:ticket-triage",
                "tool_type": "workflow",
                "status": "completed",
                "result": {"workflow_run_id": child.id},
            }
        },
    )
    db.add(
        RunCostEntry(
            run_id=parent.id,
            step_id=step.id,
            tenant_id="test-tenant",
            workspace_id="test-workspace",
            amount=Decimal("0.10"),
            unit="tokens",
            quantity=Decimal("20"),
            total_tokens=20,
        )
    )
    response = Response(
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        run_id=parent.id,
        model="model:test",
        status="completed",
        input_json={},
        output_json={"text": "done", "citations": [{"chunk_id": "chunk_1"}]},
        usage_json={},
        metadata_json={},
    )
    db.add(response)
    db.commit()
    db.refresh(response)
    db.add(
        ResponseEvent(
            tenant_id="test-tenant",
            workspace_id="test-workspace",
            response_id=response.id,
            run_id=parent.id,
            sequence=1,
            type="response.completed",
            source="agent",
            payload_json={"status": "completed"},
        )
    )
    db.commit()
    import asyncio

    asyncio.run(
        log_gateway_request(
            trace_writer=trace_writer,
            run_id=parent.id,
            step_id=step.id,
            gateway_type="tool",
            request_data={"tool_ref": "wf:ticket-triage"},
            response_data={"success": True},
        )
    )
    trace_writer.update_run_status(parent.id, "failed", error_message="demo failure")
    trace_writer.update_run_status(child.id, "succeeded")

    resp = client.get("/api/v1/observe/dashboard", headers=_headers())
    assert resp.status_code == status.HTTP_200_OK
    recent = resp.json()["data"]["recent_runs"][0]
    assert recent["run_id"] == parent.id
    assert recent["duration_ms"] is not None
    assert recent["observe_summary"] == {
        "step_count": 1,
        "tool_call_count": 1,
        "child_run_count": 1,
        "response_event_count": 1,
        "citation_count": 1,
        "audit_count": 1,
        "cost_entry_count": 1,
    }


def test_observe_dashboard_returns_tab_section_contract(client, db):
    now = utc_now()
    run = Run(
        id="run_dashboard_tabs",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="test-user",
        trace_id="trace_dashboard_tabs",
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agent:support",
        subject_version_id="agtv_tabs",
        status="failed",
        duration_ms=240,
        started_at=now,
        ended_at=now,
    )
    tool_step = RunStep(
        id="step_dashboard_tabs_tool",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        trace_id="trace_dashboard_tabs",
        run_id=run.id,
        step_id="call_search_tool",
        step_type="tool",
        node_id="tool-call",
        status="failed",
        started_at=now,
        ended_at=now,
        metrics_json={
            "latency_ms": 1400,
            "retry_count": 1,
            "tool_call": {"tool_ref": "search_tool", "status": "failed"},
        },
        error_code="timeout",
        error_message="tool timeout",
    )
    retrieval_step = RunStep(
        id="step_dashboard_tabs_retrieval",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        trace_id="trace_dashboard_tabs",
        run_id=run.id,
        step_id="retrieve_support",
        step_type="retrieval",
        node_id="knowledge-search",
        status="succeeded",
        started_at=now,
        ended_at=now,
        metrics_json={
            "knowledge_id": "knowledge:kb_support",
            "result_count": 4,
            "citation_count": 3,
            "avg_score": 0.8,
        },
    )
    cost = RunCostEntry(
        run_id=run.id,
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        amount=Decimal("1.20"),
        unit="tokens",
        quantity=Decimal("200"),
        provider="openai",
        model_ref="model:openai:gpt-5.1",
        total_tokens=200,
        created_at=now,
    )
    db.add(run)
    db.add(tool_step)
    db.add(retrieval_step)
    db.add(cost)
    db.commit()

    expected_sections = {
        "agent_health": "agent:support",
        "workflow_bottlenecks": "tool-call",
        "tool_reliability": "search_tool",
        "knowledge_quality": "knowledge:kb_support",
    }
    for tab, row_id in expected_sections.items():
        resp = client.get(
            "/api/v1/observe/dashboard",
            params={"tab": tab, "range": "1h", "bucket": "10m", "page_size": 1},
            headers=_headers(),
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()["data"]
        assert data["overview"]["workspace_health_score"] == 0.0
        assert data["overview"]["sampling_rate"] == 1.0
        assert [item["id"] for item in data["tabs"]] == [
            "agent_health",
            "workflow_bottlenecks",
            "tool_reliability",
            "knowledge_quality",
        ]
        assert len(data["metric_cards"]) == 5
        section = data["section"]
        assert section["id"] == tab
        assert "summary_cards" in section
        assert "charts" in section
        assert "rows" in section
        assert "page" in section
        assert "empty_state" in section
        assert section["page"]["page_size"] <= 1
        assert section["rows"][0]["id"] == row_id
        assert section["rows"][0]["latest_run_id"] == run.id
        assert section["rows"][0]["latest_run_cost_usd"] == 1.2
        assert section["rows"][0]["detail_url"] == f"/observe/runs/{run.id}"


def test_observe_dashboard_filters_rows_by_search(client, db):
    now = utc_now()
    run = Run(
        id="run_dashboard_search",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="test-user",
        trace_id="trace_dashboard_search",
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agent:search",
        status="succeeded",
        started_at=now,
        ended_at=now,
    )
    matching = RunStep(
        id="step_dashboard_search_matching",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        trace_id="trace_dashboard_search",
        run_id=run.id,
        step_id="call_target",
        step_type="tool",
        node_id="target-node",
        status="succeeded",
        started_at=now,
        metrics_json={"tool_call": {"tool_ref": "target_tool"}},
    )
    other = RunStep(
        id="step_dashboard_search_other",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        trace_id="trace_dashboard_search",
        run_id=run.id,
        step_id="call_other",
        step_type="tool",
        node_id="other-node",
        status="succeeded",
        started_at=now,
        metrics_json={"tool_call": {"tool_ref": "other_tool"}},
    )
    db.add(run)
    db.add(matching)
    db.add(other)
    db.commit()

    resp = client.get(
        "/api/v1/observe/dashboard",
        params={"tab": "tool_reliability", "q": "target", "range": "1h"},
        headers=_headers(),
    )

    assert resp.status_code == status.HTTP_200_OK
    rows = resp.json()["data"]["section"]["rows"]
    assert [row["id"] for row in rows] == ["target_tool"]


def test_observe_dashboard_counts_tool_call_metrics_even_when_step_type_is_not_tool(client, db):
    now = utc_now()
    run = Run(
        id="run_dashboard_tool_projection",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="test-user",
        trace_id="trace_dashboard_tool_projection",
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agent:tool-projection",
        status="succeeded",
        started_at=now,
        ended_at=now,
    )
    step = RunStep(
        id="step_dashboard_tool_projection",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        trace_id="trace_dashboard_tool_projection",
        run_id=run.id,
        step_id="planner_tool_projection",
        step_type="other",
        status="succeeded",
        started_at=now,
        ended_at=now,
        metrics_json={
            "latency_ms": 250,
            "tool_call": {
                "tool_ref": "search_tool",
                "tool_name": "search_tool",
                "status": "completed",
            },
        },
    )
    db.add(run)
    db.add(step)
    db.commit()

    resp = client.get(
        "/api/v1/observe/dashboard",
        params={"tab": "tool_reliability"},
        headers=_headers(),
    )

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["tool_health"] == [
        {
            "tool_ref": "search_tool",
            "call_count": 1,
            "failed_call_count": 0,
            "failure_rate": 0.0,
            "health_status": "healthy",
        }
    ]
    assert data["section"]["rows"][0]["id"] == "search_tool"
    assert data["section"]["rows"][0]["latest_run_id"] == run.id


def test_observe_dashboard_builds_knowledge_quality_from_response_citations(client, db):
    now = utc_now()
    run = Run(
        id="run_dashboard_response_citation",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="test-user",
        trace_id="trace_dashboard_response_citation",
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agent:citation-only",
        status="succeeded",
        started_at=now,
        ended_at=now,
    )
    response = Response(
        id="resp_dashboard_response_citation",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        run_id=run.id,
        model="model:test",
        status="completed",
        input_json={},
        output_json={
            "text": "answer",
            "citations": [
                {"knowledge_id": "knowledge:kb_support", "chunk_id": "chunk_1"},
                {"knowledge_id": "knowledge:kb_support", "chunk_id": "chunk_2"},
            ],
        },
        usage_json={},
        metadata_json={},
    )
    db.add(run)
    db.add(response)
    db.commit()

    resp = client.get(
        "/api/v1/observe/dashboard",
        params={"tab": "knowledge_quality"},
        headers=_headers(),
    )

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["knowledge_quality"] == [
        {
            "knowledge_id": "knowledge:kb_support",
            "query_count": 1,
            "failed_query_count": 0,
            "result_count": 2,
            "citation_count": 2,
            "avg_score": None,
            "failure_rate": 0.0,
            "avg_results_per_query": 2.0,
            "citation_rate": 1.0,
            "quality_status": "healthy",
        }
    ]
    assert data["section"]["rows"][0]["id"] == "knowledge:kb_support"
    assert data["section"]["rows"][0]["latest_run_id"] == run.id
