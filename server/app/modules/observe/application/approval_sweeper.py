"""Close approval requests whose run ended before anyone decided.

A run can end while one of its requests is still pending: its task, workflow
run or response was canceled, or it failed. Nothing can act on a decision
taken after that, and a request left pending would wait in every reviewer's
queue for ever. The sweeper closes such requests as ``canceled``, recorded
against the system rather than a member, and sends ``approval.canceled`` like
any other closing, so every consumer sees one terminal state.
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
from app.modules.observe.domain.models import ApprovalRequest
from app.modules.observe.infra.approval_outbox_emit import (
    enqueue_approval_canceled_outbox,
)

logger = logging.getLogger(__name__)

SYSTEM_ACTOR = "system"
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
            await close_approvals_of_ended_runs(db)
        finally:
            await db.close()

    while True:
        try:
            await _sweep()
        except Exception:
            logger.exception("Approval sweep failed")
        await asyncio.sleep(interval)
