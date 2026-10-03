"""B4: approval.approved / approval.rejected outbox consumers resume or fail tasks."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlmodel import select

from app.kernel.commons.time import utc_now
from app.kernel.events.dispatcher import OutboxDispatcher
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.status import ApprovalStatus, TaskStatus
from app.kernel.runtime.tasks.service import TaskService
from app.modules.observe.application.approval_sweeper import (
    close_approvals_of_ended_runs,
    expire_overdue_approvals,
)
from app.modules.observe.domain.models import ApprovalDecision, ApprovalRequest
from app.modules.observe.infra.repository import ApprovalRepository
from app.wiring.outbox_handlers import get_outbox_registry, register_outbox_handlers


@pytest.mark.asyncio
async def test_approval_approved_outbox_resumes_waiting_task(async_db, ctx) -> None:
    register_outbox_handlers()
    reg = get_outbox_registry()

    run = Run(
        id="run_apr_outbox_resume",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        trace_id="tr_apr_resume",
        mode="agent",
        kind="agent",
        status="running",
    )
    async_db.add(run)
    await async_db.commit()

    core = TaskService(async_db, ctx)
    task = await core.create_task(
        task_type="demo",
        status=TaskStatus.WAITING_APPROVAL.value,
        run_id=run.id,
    )

    await ApprovalRepository(async_db, ctx).create(
        ApprovalRequest(
            title="need ok",
            run_id=run.id,
            task_id=task.id,
        )
    )

    d = OutboxDispatcher(async_db, reg)
    assert await d.run_once(batch_limit=20) >= 1
    await async_db.commit()

    approval = (await async_db.exec(select(ApprovalRequest).where(ApprovalRequest.task_id == task.id))).first()
    assert approval is not None
    approval.status = ApprovalStatus.APPROVED.value
    approval.resolved_by = ctx.user_id
    approval.resolved_at = utc_now()
    await ApprovalRepository(async_db, ctx).update(approval, emit_resolution_event=ApprovalStatus.APPROVED.value)

    assert await d.run_once(batch_limit=20) >= 1
    await async_db.commit()

    assert (await core.get_task(task.id)).status == TaskStatus.RUNNING.value
    resumed = [
        event
        for event in await core.task_repo.list_events(task.id)
        if event.event_type == "task.status" and event.payload_json.get("status") == TaskStatus.RUNNING.value
    ]
    assert resumed, "the resume must be recorded on the task timeline"


@pytest.mark.asyncio
async def test_approval_rejected_outbox_fails_waiting_task(async_db, ctx) -> None:
    register_outbox_handlers()
    reg = get_outbox_registry()

    run = Run(
        id="run_apr_outbox_reject",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        trace_id="tr_apr_reject",
        mode="agent",
        kind="agent",
        status="running",
    )
    async_db.add(run)
    await async_db.commit()

    core = TaskService(async_db, ctx)
    task = await core.create_task(
        task_type="demo",
        status=TaskStatus.WAITING_APPROVAL.value,
        run_id=run.id,
    )

    await ApprovalRepository(async_db, ctx).create(
        ApprovalRequest(
            title="need no",
            run_id=run.id,
            task_id=task.id,
        )
    )

    d = OutboxDispatcher(async_db, reg)
    assert await d.run_once(batch_limit=20) >= 1
    await async_db.commit()

    approval = (await async_db.exec(select(ApprovalRequest).where(ApprovalRequest.task_id == task.id))).first()
    assert approval is not None
    approval.status = ApprovalStatus.REJECTED.value
    approval.resolved_by = ctx.user_id
    approval.resolution_note = "not today"
    approval.resolved_at = utc_now()
    await ApprovalRepository(async_db, ctx).update(approval, emit_resolution_event=ApprovalStatus.REJECTED.value)

    assert await d.run_once(batch_limit=20) >= 1
    await async_db.commit()

    failed = await core.get_task(task.id)
    assert failed.status == TaskStatus.FAILED.value
    assert failed.error_code == "approval_rejected"


async def _waiting_task(async_db, ctx, *, run_id: str, run_status: str = "running"):
    async_db.add(
        Run(
            id=run_id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            mode="agent",
            kind="agent",
            status=run_status,
        )
    )
    await async_db.commit()
    core = TaskService(async_db, ctx)
    task = await core.create_task(task_type="demo", status=TaskStatus.WAITING_APPROVAL.value, run_id=run_id)
    approval = await ApprovalRepository(async_db, ctx).create(
        ApprovalRequest(title="need ok", run_id=run_id, task_id=task.id)
    )
    return core, task, approval


@pytest.mark.asyncio
async def test_a_canceled_request_releases_its_waiting_task(async_db, ctx) -> None:
    register_outbox_handlers()
    dispatcher = OutboxDispatcher(async_db, get_outbox_registry())
    core, task, approval = await _waiting_task(async_db, ctx, run_id="run_apr_outbox_cancel")
    await dispatcher.run_once(batch_limit=20)
    await async_db.commit()

    approval.status = ApprovalStatus.CANCELED.value
    approval.resolved_by = ctx.user_id
    approval.resolved_at = utc_now()
    await ApprovalRepository(async_db, ctx).update(approval, emit_resolution_event=ApprovalStatus.CANCELED.value)
    assert await dispatcher.run_once(batch_limit=20) >= 1
    await async_db.commit()

    released = await core.get_task(task.id)
    assert released.status == TaskStatus.FAILED.value
    assert released.error_code == "approval_canceled"


@pytest.mark.asyncio
async def test_the_sweeper_closes_only_requests_of_ended_runs(async_db, ctx) -> None:
    register_outbox_handlers()
    _, _, ended = await _waiting_task(async_db, ctx, run_id="run_apr_sweep_ended", run_status="canceled")
    _, _, live = await _waiting_task(async_db, ctx, run_id="run_apr_sweep_live", run_status="waiting_approval")
    loose = await ApprovalRepository(async_db, ctx).create(ApprovalRequest(title="no run"))
    ended_id, live_id, loose_id = ended.id, live.id, loose.id

    assert await close_approvals_of_ended_runs(async_db) == 1
    assert await close_approvals_of_ended_runs(async_db) == 0

    statuses = {}
    for approval_id in (ended_id, live_id, loose_id):
        stored = await async_db.get(ApprovalRequest, approval_id)
        await async_db.refresh(stored)
        statuses[approval_id] = (stored.status, stored.resolved_by)
    assert statuses == {
        ended_id: ("canceled", "system"),
        live_id: ("pending", None),
        loose_id: ("pending", None),
    }
    events = (await async_db.exec(select(EventOutbox).where(EventOutbox.subject_id == ended_id))).all()
    types = {(row if isinstance(row, EventOutbox) else row[0]).event_type for row in events}
    assert "approval.canceled" in types


@pytest.mark.asyncio
async def test_an_undecided_request_expires_at_its_deadline_and_counts_as_a_rejection(async_db, ctx) -> None:
    register_outbox_handlers()
    dispatcher = OutboxDispatcher(async_db, get_outbox_registry())
    core, task, overdue = await _waiting_task(async_db, ctx, run_id="run_apr_expire")
    _, _, later = await _waiting_task(async_db, ctx, run_id="run_apr_expire_later")
    overdue.expires_at = utc_now() - timedelta(seconds=1)
    later.expires_at = utc_now() + timedelta(hours=1)
    async_db.add(overdue)
    async_db.add(later)
    await async_db.commit()
    overdue_id, later_id, task_id = overdue.id, later.id, task.id
    await dispatcher.run_once(batch_limit=50)
    await async_db.commit()

    assert await expire_overdue_approvals(async_db) == 1
    assert await expire_overdue_approvals(async_db) == 0
    assert await dispatcher.run_once(batch_limit=50) >= 1
    await async_db.commit()

    expired = await async_db.get(ApprovalRequest, overdue_id)
    await async_db.refresh(expired)
    untouched = await async_db.get(ApprovalRequest, later_id)
    await async_db.refresh(untouched)
    assert (expired.status, expired.resolved_by) == ("expired", "system")
    assert untouched.status == "pending"
    released = await core.get_task(task_id)
    assert (released.status, released.error_code) == (TaskStatus.FAILED.value, "approval_expired")
    history = (await async_db.exec(select(ApprovalDecision).where(ApprovalDecision.approval_id == overdue_id))).all()
    assert [(row if isinstance(row, ApprovalDecision) else row[0]).action for row in history] == ["expired"]
