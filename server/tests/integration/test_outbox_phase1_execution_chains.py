"""B6: Phase-1 execution chain acceptance — run, task, workflow node chain, approval (spec B7)."""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.events.dispatcher import OutboxDispatcher
from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.publisher import OutboxPublisher
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.tasks.service import TaskService
from app.kernel.runtime.tasks.status import ApprovalStatus, TaskStatus
from app.modules.observe.domain.models import ApprovalRequest
from app.modules.observe.infra.repository import ApprovalRepository
from app.modules.workflow.domain.models import Workflow, WorkflowRun
from app.modules.workflow.domain.workflow_events import WorkflowEventType
from app.wiring.outbox_handlers import get_outbox_registry, register_outbox_handlers


def _outbox_for_run(db: Session, run_id: str, event_type: str) -> EventOutbox:
    row = db.exec(
        select(EventOutbox).where(EventOutbox.run_id == run_id, EventOutbox.event_type == event_type)
    ).first()
    assert row is not None
    return row


@pytest.mark.asyncio
async def test_phase1_chain_run_task_workflow_nodes_and_approval(db: Session, ctx: RequestContext) -> None:
    """run.created → task.* → workflow.node.completed (with next-node enqueue) → approval.approved resume."""
    register_outbox_handlers()
    reg = get_outbox_registry()
    dispatcher = OutboxDispatcher(db, reg)

    tw = TraceWriter(db, ctx, event_bus=None)
    run = tw.create_run("workflow", kind="test", subject_kind="workflow")

    run_row = _outbox_for_run(db, run.id, "run.created")
    assert run_row.status == "pending"
    assert await dispatcher.run_once(batch_limit=30) >= 1
    db.commit()
    assert db.get(EventOutbox, run_row.id).status == "done"

    core = TaskService(db, ctx)
    task_main = core.create_task(task_type="wf_step", status=TaskStatus.QUEUED.value, run_id=run.id)
    core.transition_task(task_id=task_main.id, status=TaskStatus.RUNNING.value)
    core.transition_task(task_id=task_main.id, status=TaskStatus.SUCCEEDED.value)

    for _ in range(12):
        n = await dispatcher.run_once(batch_limit=30)
        db.commit()
        if n == 0:
            break

    task_outbox = list(db.exec(select(EventOutbox).where(EventOutbox.task_id == task_main.id)).all())
    assert len(task_outbox) >= 3
    for ob in task_outbox:
        refreshed = db.get(EventOutbox, ob.id)
        assert refreshed is not None
        assert refreshed.status == "done"

    workflow = Workflow(
        id="wf_phase1",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="phase1-workflow",
    )
    db.add(workflow)
    db.flush()

    wfr = WorkflowRun(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id=run.id,
        workflow_id=workflow.id,
        total_nodes=2,
        completed_nodes=0,
        failed_nodes=0,
        waiting_nodes=2,
    )
    db.add(wfr)
    db.flush()

    OutboxPublisher(OutboxRepository(db)).publish(
        DomainEventEnvelope(
            event_id=f"evt_wf_node_completed_{wfr.id}_n1",
            event_type=WorkflowEventType.NODE_COMPLETED,
            tenant_id=ctx.tenant_id,
            subject_type="workflow_run",
            subject_id=wfr.id,
            run_id=run.id,
            workflow_run_id=wfr.id,
            correlation_id=run.id,
            producer="test.phase1_execution_chain",
            occurred_at=utc_now(),
            payload={
                "workflow_run_id": wfr.id,
                "node_id": "n1",
                "next_node_id": "n2",
            },
        )
    )
    db.commit()

    for _ in range(8):
        n = await dispatcher.run_once(batch_limit=30)
        db.commit()
        if n == 0:
            break

    db.refresh(wfr)
    assert wfr.completed_nodes == 2
    assert wfr.waiting_nodes == 0

    wf_outbox = list(
        db.exec(select(EventOutbox).where(EventOutbox.workflow_run_id == wfr.id)).all()
    )
    assert len(wf_outbox) >= 2
    for ob in wf_outbox:
        refreshed = db.get(EventOutbox, ob.id)
        assert refreshed is not None
        assert refreshed.status == "done"

    task_wait = core.create_task(
        task_type="approval_gate",
        status=TaskStatus.WAITING_APPROVAL.value,
        run_id=run.id,
    )
    ApprovalRepository(db, ctx).create(
        ApprovalRequest(
            title="phase1 gate",
            run_id=run.id,
            task_id=task_wait.id,
        )
    )

    for _ in range(8):
        n = await dispatcher.run_once(batch_limit=30)
        db.commit()
        if n == 0:
            break

    approval = db.exec(select(ApprovalRequest).where(ApprovalRequest.task_id == task_wait.id)).first()
    assert approval is not None
    approval.status = ApprovalStatus.APPROVED.value
    approval.resolved_by = ctx.user_id
    approval.resolved_at = utc_now()
    ApprovalRepository(db, ctx).update(approval, emit_resolution_event=ApprovalStatus.APPROVED.value)

    assert await dispatcher.run_once(batch_limit=30) >= 1
    db.commit()

    assert core.get_task(task_wait.id).status == TaskStatus.RUNNING.value
