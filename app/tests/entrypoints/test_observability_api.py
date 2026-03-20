"""Entrypoint tests for the observability governance API contract."""

from decimal import Decimal

from fastapi import status

from app.kernel.trace.models import Run, RunArtifact, RunCostEntry, RunStep


def _headers() -> dict:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def test_observability_approval_feedback_and_replay_contract(client, db):
    run = Run(
        id="run_contract_observability",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="test-user",
        trace_id="trace_contract_observability",
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
        id="step_contract_observability",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        trace_id="trace_contract_observability",
        run_id=run.id,
        step_id="plan",
        step_type="agent_plan",
        status="succeeded",
        input_summary="plan in",
        output_summary="plan out",
        metrics_json={"latency_ms": 10},
    )
    artifact = RunArtifact(
        id="art_contract_observability",
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
        amount=Decimal("0.10"),
        unit="tokens",
        quantity=Decimal("2"),
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
        "/api/v1/observability/approvals",
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

    approvals_resp = client.get(f"/api/v1/observability/approvals?run_id={run.id}", headers=_headers())
    assert approvals_resp.status_code == status.HTTP_200_OK
    assert approvals_resp.json()["data"]["items"][0]["id"] == approval_id

    resolve_resp = client.post(
        f"/api/v1/observability/approvals/{approval_id}/resolve",
        json={"status": "approved", "resolution_note": "approved for contract"},
        headers=_headers(),
    )
    assert resolve_resp.status_code == status.HTTP_200_OK
    assert resolve_resp.json()["data"]["status"] == "approved"

    feedback_resp = client.post(
        "/api/v1/observability/feedback",
        json={
            "run_id": run.id,
            "thread_id": "thr_contract",
            "agent_id": "agt_contract",
            "rating": 5,
            "category": "quality",
            "comment": "looks good",
            "metadata_json": {"source": "contract"},
        },
        headers=_headers(),
    )
    assert feedback_resp.status_code == status.HTTP_201_CREATED

    list_feedback_resp = client.get(f"/api/v1/observability/feedback?run_id={run.id}", headers=_headers())
    assert list_feedback_resp.status_code == status.HTTP_200_OK
    assert list_feedback_resp.json()["data"]["items"][0]["rating"] == 5

    replay_resp = client.get(f"/api/v1/observability/runs/{run.id}/replay", headers=_headers())
    assert replay_resp.status_code == status.HTTP_200_OK
    replay = replay_resp.json()["data"]
    assert replay["run"]["id"] == run.id
    assert replay["steps"][0]["step_type"] == "agent_plan"
    assert replay["artifacts"][0]["storage_key"] == "artifacts/contract.json"
    assert replay["costs"][0]["provider"] == "test-provider"
    assert replay["approvals"][0]["id"] == approval_id
    assert replay["feedback"][0]["comment"] == "looks good"
    assert replay["trace_spec"]["run"]["run_id"] == run.id

