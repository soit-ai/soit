"""Detached execution for redriven workflow runs.

A redrive resumes the run in a process-level background task with its own
database session, exactly like first execution after the request/execution
split: only process death ends it early, and then the expired lease makes the
orphan visible to the reaper so the operator can redrive again.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlmodel import Session as SQLModelSession

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.common import lease
from app.modules.workflow.domain.models import WorkflowRun
from app.settings.settings import settings

logger = logging.getLogger(__name__)

_redrive_tasks: set[asyncio.Task] = set()


def start_detached_redrive(
    *,
    bind: Any,
    ctx: RequestContext,
    plan: Any,
    workflow_run_id: str,
    checkpoint: dict[str, Any],
) -> asyncio.Task:
    """Resume the staged run on an independent session with lease heartbeat."""

    def _session() -> SQLModelSession:
        return SQLModelSession(bind=bind, expire_on_commit=False)

    async def _execute() -> None:
        from app.wiring.services import build_workflow_service

        with _session() as probe:
            claim = probe.get(WorkflowRun, workflow_run_id)
            worker_id = claim.lease_owner if claim else None
            attempt = claim.attempt_count if claim else 0
        stop = asyncio.Event()
        lease_lost = asyncio.Event()
        heartbeat = None
        if worker_id:
            heartbeat = asyncio.create_task(
                lease.LeaseHeartbeat(
                    _session,
                    WorkflowRun,
                    workflow_run_id,
                    worker_id=worker_id,
                    attempt_count=attempt,
                    lease_seconds=lease.normalize_lease_seconds(
                        settings.workflow_execution_lease_seconds
                    ),
                    log_label="Workflow redrive lease",
                ).run(stop, lease_lost)
            )
        try:
            with _session() as exec_db:
                try:
                    service = build_workflow_service(db=exec_db, ctx=ctx)
                    await service.engine.redrive_workflow(
                        plan,
                        workflow_run_id=workflow_run_id,
                        checkpoint=checkpoint,
                    )
                except Exception:
                    # The engine already recorded the failure on the Run; the
                    # run stays a dead letter and can be redriven again.
                    logger.exception(
                        "Workflow redrive failed",
                        extra={"workflow_run_id": workflow_run_id},
                    )
                finally:
                    # The engine leaves its final run transition uncommitted;
                    # closing without committing would roll the terminal
                    # status back and strand the run.
                    exec_db.commit()
        finally:
            stop.set()
            if heartbeat is not None:
                await heartbeat

    task = asyncio.create_task(_execute())
    _redrive_tasks.add(task)
    task.add_done_callback(_redrive_tasks.discard)
    return task
