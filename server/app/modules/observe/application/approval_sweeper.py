"""Close approval requests nobody can or did decide in time.

A run can end while one of its requests is still pending: its task, workflow
run or response was canceled, or it failed. Nothing can act on a decision
taken after that, and a request left pending would wait in every reviewer's
queue for ever. The sweeper closes such requests as ``canceled``.

A request with a deadline that passed undecided closes as ``expired``, which
every consumer treats as a rejection: the call it asked about never runs.
Nothing ever approves a request on its own.

Both closings are recorded against the system rather than a member, in the
request's history and with an ``approval.*`` event like any other closing, so
every consumer sees one terminal state.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.status import ApprovalStatus
from app.modules.observe.domain.approval_policy import assignees
from app.modules.observe.domain.models import ApprovalRequest
from app.modules.observe.infra.approval_outbox_emit import (
    enqueue_approval_canceled_outbox,
    enqueue_approval_expired_outbox,
)
from app.modules.observe.infra.repository import ApprovalRepository

logger = logging.getLogger(__name__)

SYSTEM_ACTOR = "system"
EXPIRED_NOTE = "No decision before the deadline"
ENDED_RUN_STATUSES = ("succeeded", "failed", "canceled", "expired")


async def close_approvals_of_ended_runs(db: AsyncSession, *, limit: int = 100) -> int:
    """Cancel pending requests of runs that ended. Returns how many were closed.

    Requests are locked with ``SKIP LOCKED`` so concurrent sweeps, one per API
    replica, each take a distinct set; a request a member is deciding at the
    same moment is skipped and looked at again on the next sweep.
    """

    rows = (
        await db.execute(
            select(ApprovalRequest, Run.status)
            .join(Run, Run.id == ApprovalRequest.run_id)
            .where(
                ApprovalRequest.status == ApprovalStatus.PENDING.value,
                Run.tenant_id == ApprovalRequest.tenant_id,
                Run.workspace_id == ApprovalRequest.workspace_id,
                Run.status.in_(ENDED_RUN_STATUSES),
            )
            .limit(limit)
            .with_for_update(skip_locked=True, of=ApprovalRequest)
        )
    ).all()
    if not rows:
        await db.rollback()
        return 0
    now = utc_now()
    for approval, run_status in rows:
        ApprovalRepository(db, RequestContext(tenant_id=approval.tenant_id, workspace_id=approval.workspace_id, user_id=SYSTEM_ACTOR)).add_decision(
            approval,
            action=ApprovalStatus.CANCELED.value,
            actor_id=SYSTEM_ACTOR,
            actor_role=SYSTEM_ACTOR,
            note=f"Run {run_status} before a decision",
            assignees_before=assignees(approval),
        )
        approval.status = ApprovalStatus.CANCELED.value
        approval.resolved_by = SYSTEM_ACTOR
        approval.resolution_note = f"Run {run_status} before a decision"
        approval.resolved_at = now
        approval.updated_at = now
        db.add(approval)
        ctx = RequestContext(
            tenant_id=approval.tenant_id,
            workspace_id=approval.workspace_id,
            user_id=SYSTEM_ACTOR,
        )
        enqueue_approval_canceled_outbox(db, ctx, approval=approval)
        logger.info(
            "Closed approval request of an ended run",
            extra={"approval_id": approval.id, "run_id": approval.run_id, "run_status": run_status},
        )
    await db.commit()
    return len(rows)


async def expire_overdue_approvals(db: AsyncSession, *, limit: int = 100) -> int:
    """Close pending requests whose deadline passed as ``expired``. Returns how many.

    Locked with ``SKIP LOCKED`` like the ended-run sweep: a request a member
    is deciding right now is left to that decision, which itself refuses a
    request past its deadline.
    """

    now = utc_now()
    rows = (
        await db.execute(
            select(ApprovalRequest)
            .where(
                ApprovalRequest.status == ApprovalStatus.PENDING.value,
                ApprovalRequest.expires_at.is_not(None),
                ApprovalRequest.expires_at <= now,
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    if not rows:
        await db.rollback()
        return 0
    for approval in rows:
        close_as_expired(db, approval, now=now)
        logger.info("Expired an undecided approval request", extra={"approval_id": approval.id})
    await db.commit()
    return len(rows)


def close_as_expired(db: AsyncSession, approval: ApprovalRequest, *, now) -> None:
    """Mark ``approval`` expired, record it and queue its event; the caller commits."""

    ctx = RequestContext(tenant_id=approval.tenant_id, workspace_id=approval.workspace_id, user_id=SYSTEM_ACTOR)
    ApprovalRepository(db, ctx).add_decision(
        approval,
        action=ApprovalStatus.EXPIRED.value,
        actor_id=SYSTEM_ACTOR,
        actor_role=SYSTEM_ACTOR,
        note=EXPIRED_NOTE,
        assignees_before=assignees(approval),
    )
    approval.status = ApprovalStatus.EXPIRED.value
    approval.resolved_by = SYSTEM_ACTOR
    approval.resolution_note = EXPIRED_NOTE
    approval.resolved_at = now
    approval.updated_at = now
    db.add(approval)
    enqueue_approval_expired_outbox(db, ctx, approval=approval)


async def run_approval_sweeper_loop(
    db_factory: Callable[[], AsyncSession],
    *,
    interval_seconds: float,
) -> None:
    """Periodically close the requests of ended runs."""

    interval = max(5.0, float(interval_seconds or 0))

    async def _sweep() -> None:
        db = db_factory()
        try:
            await expire_overdue_approvals(db)
            await close_approvals_of_ended_runs(db)
        finally:
            await db.close()

    while True:
        try:
            await _sweep()
        except Exception:
            logger.exception("Approval sweep failed")
        await asyncio.sleep(interval)
