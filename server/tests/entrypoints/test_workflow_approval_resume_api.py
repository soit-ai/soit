"""A workflow run stopped for approval resumes only on a decision.

Resuming reads the request the run waits on: a pending request, or none at
all, keeps the run waiting, and the decision that was taken is what the
resumed node acts on. Only ``approved`` lets the tool call run.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import status

from app.kernel.commons.ids import generate_run_id
from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.runs import Run
from app.modules.observe.domain.models import ApprovalRequest
from app.modules.workflow.domain.models import WorkflowRun
from app.modules.workflow.runtime.engine import ExecutionEngine

pytestmark = pytest.mark.asyncio

GRAPH = {
    "name": "gated",
    "inputs_schema": {"type": "object", "properties": {"ticket_id": {"type": "string"}}},
    "outputs_schema": {
        "type": "object",
        "properties": {
            "value": {
                "type": "object",
                "properties": {"ticket_id": {"type": "string"}},
                "required": ["ticket_id"],
            }
        },
        "required": ["value"],
    },
    "graph": {
        "nodes": [
            {"id": "set_ticket", "type": "set_var", "params": {"key": "ticket_id", "value": "{{ inputs.ticket_id }}"}},
            {"id": "out1", "type": "output", "params": {"value": {"ticket_id": "{{ steps.set_ticket.output.value }}"}}},
        ],
        "edges": [{"id": "e1", "from": "set_ticket", "to": "out1"}],
    },
}


async def _waiting_run(async_client, async_db, ctx, *, approval_status: str | None) -> tuple[str, str]:
    created = await async_client.post("/api/v1/workflows", json={"name": "gated_workflow"})
    assert created.status_code == status.HTTP_201_CREATED, created.text
    workflow_id = created.json()["data"]["id"]
    version = await async_client.post(f"/api/v1/workflows/{workflow_id}/versions", json={"graph_json": GRAPH})
    assert version.status_code == status.HTTP_201_CREATED, version.text
    version_id = version.json()["data"]["id"]

    scope = {"tenant_id": ctx.tenant_id, "workspace_id": ctx.workspace_id}
    run = Run(
        id=generate_run_id(),
        user_id=ctx.user_id,
        mode="workflow",
        kind="workflow",
        status="waiting_approval",
        subject_kind="workflow",
        subject_id=workflow_id,
        subject_version_id=version_id,
        started_at=utc_now(),
        **scope,
    )
    async_db.add(run)
    await async_db.flush()
    async_db.add(
        WorkflowRun(
            run_id=run.id,
            workflow_id=workflow_id,
            status="waiting_approval",
            checkpoint_json={
                "inputs": {"ticket_id": "T-1"},
                "waiting_node_id": "send",
                "tool_call_id": "call_send",
            },
            **scope,
        )
    )
    if approval_status is not None:
        async_db.add(
            ApprovalRequest(
                run_id=run.id,
                title="Approve tool call: tool:test:send",
                status=approval_status,
                details_json={"tool_call_id": "call_send", "node_id": "send"},
                **scope,
            )
        )
    await async_db.commit()
    return workflow_id, run.id


@pytest.fixture
def resumed(monkeypatch) -> list[dict[str, Any]]:
    """What the engine was asked to resume with; the graph itself is not run."""

    calls: list[dict[str, Any]] = []

    async def _resume(self, plan, *, workflow_run_id, checkpoint, approval_status):
        del self, plan, checkpoint
        calls.append({"approval_status": approval_status, "workflow_run_id": workflow_run_id})
        return {"status": "succeeded"}

    monkeypatch.setattr(ExecutionEngine, "resume_workflow", _resume)
    return calls


@pytest.mark.parametrize("approval_status", ["pending", None])
async def test_a_run_without_a_decision_does_not_resume(async_client, async_db, ctx, resumed, approval_status) -> None:
    workflow_id, run_id = await _waiting_run(async_client, async_db, ctx, approval_status=approval_status)

    response = await async_client.post(f"/api/v1/workflows/{workflow_id}/runs/{run_id}/resume")

    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    assert resumed == []
    run = await async_db.get(Run, run_id)
    await async_db.refresh(run)
    assert run.status == "waiting_approval"


@pytest.mark.parametrize("approval_status", ["approved", "rejected", "canceled", "expired"])
async def test_the_decision_is_what_the_run_resumes_with(async_client, async_db, ctx, resumed, approval_status) -> None:
    workflow_id, run_id = await _waiting_run(async_client, async_db, ctx, approval_status=approval_status)

    response = await async_client.post(f"/api/v1/workflows/{workflow_id}/runs/{run_id}/resume")

    assert response.status_code == status.HTTP_200_OK, response.text
    assert [call["approval_status"] for call in resumed] == [approval_status]
