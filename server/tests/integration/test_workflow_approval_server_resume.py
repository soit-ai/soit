"""A workflow run stopped for approval continues on the server once it is decided.

Nobody has to resume the run: the decision event resumes it, as the member who
started it, exactly once however often the event arrives and whoever resumes
it by hand at the same time. Only an approved call runs.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from sqlmodel import select

from app.kernel.events.dispatcher import OutboxDispatcher
from app.kernel.identity.workspace_access import WorkspaceAccess
from app.kernel.registry.deps import get_registry
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run, RunStepToolCall
from app.wiring.outbox_handlers import get_outbox_registry, register_outbox_handlers

pytestmark = pytest.mark.asyncio

GATED = "tool:function:gated_random"


def _register_gated_tool(ctx) -> None:
    get_registry().register(
        kind="tool",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name=GATED,
        version="1.0.0",
        payload={
            "tool_spec": {
                "name": "gated_random",
                "description": "A random integer, once someone has approved it",
                "adapter": "function",
                "input_schema": {
                    "type": "object",
                    "properties": {"min": {"type": "integer"}, "max": {"type": "integer"}},
                    "required": ["min", "max"],
                },
                "output_schema": {"type": "object"},
                "policy": {"audit_level": "basic", "approval": {"mode": "required", "risk_level": "high"}},
                "function": {"entrypoint": "app.utils.builtin_tools:random_int"},
            }
        },
    )


@pytest.fixture(autouse=True)
def _ledger_on_the_test_database(async_db, monkeypatch):
    """The approval ledger writes on a session of its own; point it at the test database."""

    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlmodel.ext.asyncio.session import AsyncSession

    factory = async_sessionmaker(bind=async_db.bind, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr("app.infra.db.session.get_async_session_local", lambda: factory)


@pytest.fixture
def detached(monkeypatch) -> list[asyncio.Task]:
    """The resumes the consumer started, so the test can wait for them."""

    from app.wiring import workflow_redrive

    started: list[asyncio.Task] = []
    original = workflow_redrive.start_detached_approval_resume

    def _start(**kwargs: Any) -> asyncio.Task:
        task = original(**kwargs)
        started.append(task)
        return task

    monkeypatch.setattr(workflow_redrive, "start_detached_approval_resume", _start)

    async def _member(self, tenant_id, workspace_id, user_id, session_id=None):
        del self, tenant_id, workspace_id, user_id, session_id
        return WorkspaceAccess(tenant_role="Owner", workspace_role="Owner")

    monkeypatch.setattr(
        "app.modules.identity.infra.workspace_access.DatabaseWorkspaceAccessResolver.resolve", _member
    )
    return started


async def _waiting_workflow(async_client, ctx) -> tuple[str, str, str]:
    _register_gated_tool(ctx)
    workflow_id = (await async_client.post("/api/v1/workflows", json={"name": "gated_flow"})).json()["data"]["id"]
    version = await async_client.post(
        f"/api/v1/workflows/{workflow_id}/versions",
        json={
            "graph_json": {
                "name": "gated-flow",
                "inputs_schema": {"type": "object", "properties": {"low": {"type": "integer"}}},
                "outputs_schema": {"type": "object", "properties": {"value": {"type": "object"}}},
                "graph": {
                    "nodes": [
                        {
                            "id": "draw",
                            "type": "tool",
                            "params": {"tool_ref": GATED, "arguments": {"min": 5, "max": 5}},
                        },
                        {"id": "out1", "type": "output", "params": {"value": {"drawn": "{{ steps.draw.output.result.value }}"}}},
                    ],
                    "edges": [{"id": "e1", "from": "draw", "to": "out1"}],
                },
            }
        },
    )
    assert version.status_code == 201, version.text
    version_id = version.json()["data"]["id"]
    published = await async_client.post(f"/api/v1/workflows/{workflow_id}/publish", json={"version_id": version_id})
    assert published.status_code == 200, published.text
    executed = await async_client.post(f"/api/v1/workflows/{workflow_id}/execute", json={"low": 5})
    assert executed.status_code == 200, executed.text
    run_id = executed.json()["data"]["run_id"]
    approvals = (await async_client.get("/api/v1/observe/approvals", params={"run_id": run_id})).json()["data"]["items"]
    assert len(approvals) == 1, approvals
    return workflow_id, run_id, approvals[0]["id"]


async def _deliver(async_db) -> None:
    register_outbox_handlers()
    await OutboxDispatcher(async_db, get_outbox_registry()).run_once(batch_limit=50)
    await async_db.commit()


async def _tool_calls(async_db, run_id: str) -> list[RunStepToolCall]:
    rows = (await async_db.exec(select(RunStepToolCall).where(RunStepToolCall.run_id == run_id))).all()
    calls = [row if isinstance(row, RunStepToolCall) else row[0] for row in rows]
    for call in calls:
        await async_db.refresh(call)
    return calls


async def test_an_approved_workflow_continues_on_the_server_once(async_client, async_db, ctx, detached) -> None:
    workflow_id, run_id, approval_id = await _waiting_workflow(async_client, ctx)
    await _deliver(async_db)  # approval.requested

    decided = await async_client.post(f"/api/v1/observe/approvals/{approval_id}/resolve", json={"status": "approved"})
    assert decided.status_code == 200, decided.text
    await _deliver(async_db)
    assert len(detached) == 1
    await asyncio.wait_for(asyncio.gather(*detached), timeout=30)

    run = await async_db.get(Run, run_id)
    await async_db.refresh(run)
    assert run.status == "succeeded", run.error_message
    [call] = await _tool_calls(async_db, run_id)
    assert call.status == "succeeded"

    # The event delivered again, and a member resuming by hand, change nothing.
    from app.wiring.workflow_approval_resume import handle_workflow_approval_decision

    event = (
        await async_db.exec(select(EventOutbox).where(EventOutbox.event_type == "approval.approved"))
    ).first()
    await handle_workflow_approval_decision(async_db, event if isinstance(event, EventOutbox) else event[0])
    by_hand = await async_client.post(f"/api/v1/workflows/{workflow_id}/runs/{run_id}/resume")
    assert len(detached) == 1
    assert by_hand.status_code == 400
    assert len(await _tool_calls(async_db, run_id)) == 1


async def test_a_rejected_workflow_ends_on_the_server_without_the_call(async_client, async_db, ctx, detached) -> None:
    _, run_id, approval_id = await _waiting_workflow(async_client, ctx)
    await _deliver(async_db)

    await async_client.post(f"/api/v1/observe/approvals/{approval_id}/resolve", json={"status": "rejected"})
    await _deliver(async_db)
    await asyncio.wait_for(asyncio.gather(*detached), timeout=30)

    run = await async_db.get(Run, run_id)
    await async_db.refresh(run)
    assert (run.status, run.error_code) == ("failed", "APPROVAL_REJECTED")
    [call] = await _tool_calls(async_db, run_id)
    assert call.status == "rejected"


@pytest.mark.usefixtures("detached")
async def test_a_resume_by_hand_loses_to_a_claim_already_made(async_client, async_db, ctx) -> None:
    from app.wiring.services import build_workflow_service

    workflow_id, run_id, approval_id = await _waiting_workflow(async_client, ctx)
    await async_client.post(f"/api/v1/observe/approvals/{approval_id}/resolve", json={"status": "approved"})
    await build_workflow_service(db=async_db, ctx=ctx).prepare_approval_resume(run_id)

    by_hand = await async_client.post(f"/api/v1/workflows/{workflow_id}/runs/{run_id}/resume")

    assert by_hand.status_code == 409, by_hand.text
    assert len(await _tool_calls(async_db, run_id)) == 1
    [call] = await _tool_calls(async_db, run_id)
    assert call.status == "waiting_approval"


async def test_a_run_whose_starter_left_is_not_resumed(async_client, async_db, ctx, detached, monkeypatch) -> None:
    _, run_id, approval_id = await _waiting_workflow(async_client, ctx)
    await _deliver(async_db)

    async def _gone(self, tenant_id, workspace_id, user_id, session_id=None):
        del self, tenant_id, workspace_id, user_id, session_id
        return None

    monkeypatch.setattr("app.modules.identity.infra.workspace_access.DatabaseWorkspaceAccessResolver.resolve", _gone)
    await async_client.post(f"/api/v1/observe/approvals/{approval_id}/resolve", json={"status": "approved"})
    await _deliver(async_db)

    run = await async_db.get(Run, run_id)
    await async_db.refresh(run)
    assert detached == []
    assert run.status == "waiting_approval"
