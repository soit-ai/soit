"""B4: approval.approved / approval.rejected outbox consumers resume or fail tasks."""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.kernel.commons.time import utc_now
from app.kernel.events.dispatcher import OutboxDispatcher
from app.kernel.runtime.contracts.status import ApprovalStatus, TaskStatus
from app.kernel.runtime.core.service import RuntimeCoreService
from app.kernel.trace.models import Run
from app.modules.observability.domain.models import ApprovalRequest
from app.modules.observability.infra.repository import ApprovalRepository
from app.wiring.outbox_handlers import get_outbox_registry, register_outbox_handlers


@pytest.mark.asyncio
async def test_approval_approved_outbox_resumes_waiting_task(db: Session, ctx) -> None:
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
    db.add(run)
    db.commit()

    core = RuntimeCoreService(db, ctx)
    task = core.create_task(
        task_type="demo",
        status=TaskStatus.WAITING_APPROVAL.value,
        run_id=run.id,
    )

    ApprovalRepository(db, ctx).create(
        ApprovalRequest(
            title="need ok",
            run_id=run.id,
            task_id=task.id,
        )
    )

    d = OutboxDispatcher(db, reg)
    assert await d.run_once(batch_limit=20) >= 1
    db.commit()

    approval = db.exec(select(ApprovalRequest).where(ApprovalRequest.task_id == task.id)).first()
    assert approval is not None
    approval.status = ApprovalStatus.APPROVED.value
    approval.resolved_by = ctx.user_id
    approval.resolved_at = utc_now()
    ApprovalRepository(db, ctx).update(approval, emit_resolution_event=ApprovalStatus.APPROVED.value)

    assert await d.run_once(batch_limit=20) >= 1
    db.commit()

    assert core.get_task(task.id).status == TaskStatus.RUNNING.value


@pytest.mark.asyncio
async def test_approval_rejected_outbox_fails_waiting_task(db: Session, ctx) -> None:
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
    db.add(run)
    db.commit()

    core = RuntimeCoreService(db, ctx)
    task = core.create_task(
        task_type="demo",
        status=TaskStatus.WAITING_APPROVAL.value,
        run_id=run.id,
    )

    ApprovalRepository(db, ctx).create(
        ApprovalRequest(
            title="need no",
            run_id=run.id,
            task_id=task.id,
        )
    )

    d = OutboxDispatcher(db, reg)
    assert await d.run_once(batch_limit=20) >= 1
    db.commit()

    approval = db.exec(select(ApprovalRequest).where(ApprovalRequest.task_id == task.id)).first()
    assert approval is not None
    approval.status = ApprovalStatus.REJECTED.value
    approval.resolved_by = ctx.user_id
    approval.resolution_note = "not today"
    approval.resolved_at = utc_now()
    ApprovalRepository(db, ctx).update(approval, emit_resolution_event=ApprovalStatus.REJECTED.value)

    assert await d.run_once(batch_limit=20) >= 1
    db.commit()

    failed = core.get_task(task.id)
    assert failed.status == TaskStatus.FAILED.value
    assert failed.error_code == "approval_rejected"
