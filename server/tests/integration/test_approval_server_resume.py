"""A decided approval resumes a paused agent run without a client connected.

The run's paused interaction is the checkpoint: once every approval the run
waits on is decided, the approval consumer queues a child interaction carrying
the decisions for the durable interaction worker, exactly once, and leaves a
checkpoint that a client is already resuming alone.
"""

from __future__ import annotations

from dataclasses import asdict

import pytest
from sqlmodel import select

from app.kernel.commons.time import utc_now
from app.kernel.events.dispatcher import OutboxDispatcher
from app.kernel.runtime.db.models.responses import Response, ResponseInteraction
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.responses.approval_resume import (
    RESUME_ENTRIES_KEY,
    RESUME_EXECUTION_KEY,
)
from app.kernel.runtime.status import ApprovalStatus, TaskStatus
from app.kernel.runtime.tasks.service import TaskService
from app.modules.observe.domain.models import ApprovalRequest
from app.modules.observe.infra.repository import ApprovalRepository
from app.wiring.outbox_handlers import get_outbox_registry, register_outbox_handlers

pytestmark = pytest.mark.asyncio

PARENT_ID = "ixn_paused_parent"


async def _paused_agent_run(async_db, ctx, *, interrupts: list[str]):
    run = Run(
        id="run_paused_agent",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        trace_id="tr_paused_agent",
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agent_paused",
        status="waiting_approval",
    )
    async_db.add(run)
    await async_db.commit()
    task = await TaskService(async_db, ctx).create_task(
        task_type="agent.stream",
        status=TaskStatus.WAITING_APPROVAL.value,
        agent_id="agent_paused",
        thread_id="thread_paused",
        run_id=run.id,
    )
    response = Response(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id=run.id,
        task_id=task.id,
        thread_id="thread_paused",
        agent_id="agent_paused",
        status="running",
        created_by=ctx.user_id,
    )
    async_db.add(response)
    await async_db.flush()
    parent = ResponseInteraction(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        interaction_id=PARENT_ID,
        parent_interaction_id=None,
        response_id=response.id,
        run_id=run.id,
        thread_id="thread_paused",
        request_hash=PARENT_ID,
        execution_json={
            "mode": "agent",
            "agent_id": "agent_paused",
            "agent_inputs": {
                "messages": [{"role": "user", "content": "delete the stale branch"}],
                "_agui_context": {"message_id": "msg_user_1", "assistant_message_id": "msg_old"},
                "_attachment_ids": ["att_1"],
            },
            "assistant_message_id": "msg_old",
            "payload": {"agent_id": "agent_paused"},
        },
        request_context_json=asdict(ctx),
        kind="run",
        status="waiting_approval",
        created_by=ctx.user_id,
    )
    async_db.add(parent)
    repo = ApprovalRepository(async_db, ctx)
    for interrupt_id in interrupts:
        await repo.create(
            ApprovalRequest(
                title=f"approve {interrupt_id}",
                run_id=run.id,
                task_id=task.id,
                thread_id="thread_paused",
                agent_id="agent_paused",
                details_json={"interrupt_id": interrupt_id},
            )
        )
    await async_db.commit()
    return run, task, response


async def _decide(async_db, ctx, interrupt_id: str, status: str) -> None:
    rows = (
        await async_db.exec(select(ApprovalRequest).where(ApprovalRequest.status == "pending"))
    ).all()
    approval = next(
        row for row in rows if (row.details_json or {}).get("interrupt_id") == interrupt_id
    )
    approval.status = status
    approval.resolved_by = "approver-1"
    approval.resolved_at = utc_now()
    await ApprovalRepository(async_db, ctx).update(approval, emit_resolution_event=status)


async def _dispatch(async_db) -> None:
    register_outbox_handlers()
    dispatcher = OutboxDispatcher(async_db, get_outbox_registry())
    while await dispatcher.run_once(batch_limit=50):
        pass
    await async_db.commit()


async def _interactions(async_db) -> dict[str, ResponseInteraction]:
    rows = (await async_db.exec(select(ResponseInteraction))).all()
    items = [row if isinstance(row, ResponseInteraction) else row[0] for row in rows]
    for item in items:
        await async_db.refresh(item)
    return {item.interaction_id: item for item in items}


async def test_the_last_decision_queues_one_resume_with_every_decision(async_db, ctx) -> None:
    run, task, response = await _paused_agent_run(async_db, ctx, interrupts=["int_a", "int_b"])
    await _dispatch(async_db)

    await _decide(async_db, ctx, "int_a", ApprovalStatus.APPROVED.value)
    await _dispatch(async_db)
    interactions = await _interactions(async_db)
    assert list(interactions) == [PARENT_ID], "one decision out of two must not resume the run"
    assert interactions[PARENT_ID].status == "waiting_approval"

    await _decide(async_db, ctx, "int_b", ApprovalStatus.REJECTED.value)
    await _dispatch(async_db)
    interactions = await _interactions(async_db)
    children = [item for item in interactions.values() if item.interaction_id != PARENT_ID]
    assert len(children) == 1
    child = children[0]
    parent = interactions[PARENT_ID]

    assert child.status == "queued"
    assert child.parent_interaction_id == PARENT_ID
    assert child.thread_id == "thread_paused"
    assert child.request_context_json == asdict(ctx)
    assert parent.status == "resuming"
    assert parent.resume_interaction_id == child.interaction_id

    job = child.execution_json
    inputs = job["agent_inputs"]
    decisions = {entry["interrupt_id"]: entry["payload"]["decision"] for entry in inputs[RESUME_ENTRIES_KEY]}
    assert decisions == {"int_a": "approved", "int_b": "rejected"}
    assert inputs[RESUME_EXECUTION_KEY] == {
        "run_id": run.id,
        "task_id": task.id,
        "thread_id": "thread_paused",
        "agent_id": "agent_paused",
        "response_id": response.id,
    }
    assert "_attachment_ids" not in inputs
    assert job["assistant_message_id"] not in {"msg_old", None}
    assert inputs["_agui_context"]["assistant_message_id"] == job["assistant_message_id"]
    assert inputs["_agui_context"]["message_id"] == "msg_user_1"
    # The resumed execution moves the task out of waiting when it starts.
    assert (await TaskService(async_db, ctx).get_task(task.id)).status == TaskStatus.WAITING_APPROVAL.value


async def test_redelivered_decisions_do_not_queue_a_second_resume(async_db, ctx) -> None:
    await _paused_agent_run(async_db, ctx, interrupts=["int_only"])
    await _dispatch(async_db)
    await _decide(async_db, ctx, "int_only", ApprovalStatus.APPROVED.value)
    await _dispatch(async_db)

    # A second consumer pass over the same state finds the checkpoint claimed.
    from app.modules.observe.handlers.on_approval_outbox import (
        handle_approval_approved_outbox,
    )

    approval = (await async_db.exec(select(ApprovalRequest))).first()
    replay = type("Row", (), {"payload_json": {"approval_id": approval.id}, "subject_id": approval.id})()
    await handle_approval_approved_outbox(async_db, replay)  # type: ignore[arg-type]
    await async_db.commit()

    interactions = await _interactions(async_db)
    assert len(interactions) == 2


async def test_a_checkpoint_the_client_is_resuming_is_left_alone(async_db, ctx) -> None:
    _, task, _ = await _paused_agent_run(async_db, ctx, interrupts=["int_client"])
    await _dispatch(async_db)
    parent = (await _interactions(async_db))[PARENT_ID]
    parent.status = "resuming"
    parent.resume_interaction_id = "ixn_client_resume"
    async_db.add(parent)
    await async_db.commit()

    await _decide(async_db, ctx, "int_client", ApprovalStatus.REJECTED.value)
    await _dispatch(async_db)

    assert list(await _interactions(async_db)) == [PARENT_ID]
    # Neither a second resume nor the non-agent fallback that fails the task.
    assert (await TaskService(async_db, ctx).get_task(task.id)).status == TaskStatus.WAITING_APPROVAL.value
