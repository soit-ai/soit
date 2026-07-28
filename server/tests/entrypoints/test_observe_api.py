"""Entrypoint tests for the observe governance API contract."""

from decimal import Decimal

from fastapi import status

from app.kernel.ports.common.audit import log_gateway_request
from app.kernel.runtime.db.models.runs import Run, RunArtifact, RunCostEntry, RunStep
from app.kernel.runtime.runs.writer import TraceWriter


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def test_observe_approval_feedback_and_replay_contract(client, db):
    run = Run(
        id="run_contract_observe",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="test-user",
        trace_id="trace_contract_observe",
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agt_contract",
        subject_version_id="agtv_contract",
        status="succeeded",
        input_summary="hello",
        output_summary="world",
    )
    step = RunStep(
        id="step_contract_observe",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        trace_id="trace_contract_observe",
        run_id=run.id,
        step_id="plan",
        step_type="agent_plan",
        status="succeeded",
        input_summary="plan in",
        output_summary="plan out",
        metrics_json={"latency_ms": 10},
    )
    artifact = RunArtifact(
        id="art_contract_observe",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        run_id=run.id,
        type="json",
        storage_key="artifacts/contract.json",
        meta_json={"kind": "contract"},
    )
    cost = RunCostEntry(
        run_id=run.id,
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        currency="USD",
        amount=Decimal("0.10"),
        billing_basis="tokens",
        billed_quantity=Decimal("2"),
        provider="test-provider",
        model_ref="model:test",
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=2,
    )
    db.add(run)
    db.add(step)
    db.add(artifact)
    db.add(cost)
    db.commit()

    approval_resp = client.post(
        "/api/v1/observe/approvals",
        json={
            "run_id": run.id,
            "task_id": "task_contract",
            "thread_id": "thr_contract",
            "agent_id": "agt_contract",
            "title": "Need approval",
            "policy_ref": "policy:test",
            "details_json": {"risk": "medium"},
        },
        headers=_headers(),
    )
    assert approval_resp.status_code == status.HTTP_201_CREATED
    approval = approval_resp.json()["data"]
    approval_id = approval["id"]
    assert approval["status"] == "pending"

    approvals_resp = client.get(f"/api/v1/observe/approvals?run_id={run.id}", headers=_headers())
    assert approvals_resp.status_code == status.HTTP_200_OK
    assert approvals_resp.json()["data"]["items"][0]["id"] == approval_id

    resolve_resp = client.post(
        f"/api/v1/observe/approvals/{approval_id}/resolve",
        json={"status": "approved", "resolution_note": "approved for contract"},
        headers=_headers(),
    )
    assert resolve_resp.status_code == status.HTTP_200_OK
    assert resolve_resp.json()["data"]["status"] == "approved"

    feedback_resp = client.post(
        "/api/v1/observe/feedback",
        json={
            "run_id": run.id,
            "agent_id": "agt_contract",
            "rating": 5,
            "category": "quality",
            "comment": "looks good",
            "metadata_json": {"source": "contract"},
        },
        headers=_headers(),
    )
    assert feedback_resp.status_code == status.HTTP_201_CREATED

    list_feedback_resp = client.get(f"/api/v1/observe/feedback?run_id={run.id}", headers=_headers())
    assert list_feedback_resp.status_code == status.HTTP_200_OK
    assert list_feedback_resp.json()["data"]["items"][0]["rating"] == 5

    replay_resp = client.get(f"/api/v1/observe/runs/{run.id}/replay", headers=_headers())
    assert replay_resp.status_code == status.HTTP_200_OK
    replay = replay_resp.json()["data"]
    assert replay["run"]["id"] == run.id
    assert replay["steps"][0]["step_type"] == "agent_plan"
    assert replay["artifacts"][0]["storage_key"] == "artifacts/contract.json"
    assert replay["costs"][0]["provider"] == "test-provider"
    assert replay["approvals"][0]["id"] == approval_id
    assert replay["feedback"][0]["comment"] == "looks good"
    assert replay["trace_spec"]["run"]["run_id"] == run.id


def test_observe_feedback_rejects_an_unscoped_run_reference(client):
    response = client.post(
        "/api/v1/observe/feedback",
        json={
            "run_id": "run_outside_workspace",
            "rating": 1,
            "category": "chat_response",
            "metadata_json": {"message_id": "message_unknown"},
        },
        headers=_headers(),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_workspace_audit_query_api_filters_governed_calls(client, db, ctx):
    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(mode="agent", subject_kind="agent", subject_id="agent_audit_api")
    step = trace_writer.create_step(run_id=run.id, step_type="tool", step_id="step_tool_api")

    client.portal.call(
        lambda: log_gateway_request(
            trace_writer=trace_writer,
            run_id=run.id,
            step_id=step.id,
            gateway_type="tool",
            request_data={"tool_ref": "tool:http:request"},
            response_data={"success": True},
        )
    )

    response = client.get(
        "/api/v1/runs/audits",
        params={"step_type": "tool", "gateway_type": "tool", "page_size": 10},
        headers=_headers(),
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["data"]
    assert payload["items"][0]["run_id"] == run.id
    assert payload["items"][0]["gateway_type"] == "tool"

