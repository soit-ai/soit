"""Fail workflow runs orphaned by a dead executor.

A workflow whose process died mid-execution stops renewing its lease but keeps
its "running" status. Nothing can finish it: automatic re-execution is not
offered because workflow nodes cause external side effects and per-node
idempotency across attempts is undefined. Leaving the row running would report
work that will never complete, so the reaper turns it into an honest failure
the operator can see and re-run deliberately.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.runs import Run
from app.modules.workflow.domain.models import WorkflowRun

logger = logging.getLogger(__name__)

ORPHANED_ERROR_CODE = "WORKFLOW_EXECUTION_ORPHANED"
ORPHANED_ERROR_MESSAGE = (
    "Workflow execution was interrupted (its worker stopped renewing the "
    "lease) and cannot be resumed automatically; re-run it if needed"
)

_TERMINAL_RUN_STATUSES = {"succeeded", "failed", "canceled", "expired"}


def reap_orphaned_workflow_runs(db: Session, *, limit: int = 50) -> int:
    """Fail running workflow rows whose lease expired. Returns rows reaped."""
    now = utc_now()
    orphans = (
        db.execute(
            select(WorkflowRun)
            .where(
                WorkflowRun.status == "running",
                WorkflowRun.lease_expires_at.is_not(None),
                WorkflowRun.lease_expires_at < now,
            )
            .limit(limit)
        )
        .scalars()
        .all()
    )
    reaped = 0
    for row in orphans:
        row.status = "failed"
        row.lease_owner = None
        row.lease_expires_at = None
        row.updated_at = now
        db.add(row)

        run = db.get(Run, row.run_id)
        if run is not None and run.status not in _TERMINAL_RUN_STATUSES:
            run.status = "failed"
            run.error_code = ORPHANED_ERROR_CODE
            run.error_message = ORPHANED_ERROR_MESSAGE
            run.ended_at = now
            run.updated_at = now
            db.add(run)

        logger.warning(
            "Failed orphaned workflow run",
            extra={"workflow_run_id": row.id, "run_id": row.run_id},
        )
        reaped += 1
    if reaped:
        db.commit()
    return reaped


async def run_reaper_loop(
    db_factory: Callable[[], Session],
    *,
    interval_seconds: float,
) -> None:
    """Periodically sweep for orphaned workflow runs."""
    interval = max(5.0, float(interval_seconds or 0))

    def _sweep() -> None:
        db = db_factory()
        try:
            reap_orphaned_workflow_runs(db)
        finally:
            db.close()

    while True:
        try:
            # The sweep is synchronous database work; keep it off the event
            # loop so a slow query cannot stall the API process.
            await asyncio.to_thread(_sweep)
        except Exception:
            logger.exception("Workflow orphan sweep failed")
        await asyncio.sleep(interval)
