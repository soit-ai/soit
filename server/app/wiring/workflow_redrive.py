"""Detached execution for redriven and approval-resumed workflow runs.

A redrive, or the resume of a run whose approval was decided, continues the
run in a process-level background task with its own database session,
exactly like first execution after the request/execution split: only process
death ends it early, and then the expired lease makes the orphan visible to
the reaper.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

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

    async def _redrive(service: Any) -> None:
        await service.engine.redrive_workflow(
            plan,
            workflow_run_id=workflow_run_id,
            checkpoint=checkpoint,
        )

    return _start_detached(
        bind=bind, ctx=ctx, workflow_run_id=workflow_run_id, label="Workflow redrive", execute=_redrive
    )


def start_detached_approval_resume(*, bind: Any, ctx: RequestContext, prepared: Any) -> asyncio.Task:
    """Continue a run claimed for its approval resume, as the member who started it."""

    async def _resume(service: Any) -> None:
        await service.engine.resume_workflow(
            prepared.plan,
            workflow_run_id=prepared.workflow_run_id,
            checkpoint=prepared.checkpoint,
            approval_status=prepared.approval_status,
            resume_statuses=("queued",),
        )

    return _start_detached(
        bind=bind,
        ctx=ctx,
        workflow_run_id=prepared.workflow_run_id,
        label="Workflow approval resume",
        execute=_resume,
        expected_lease_owner=prepared.lease_owner,
    )


def _start_detached(
    *,
    bind: Any,
    ctx: RequestContext,
    workflow_run_id: str,
    label: str,
    execute: Any,
    expected_lease_owner: str | None = None,
) -> asyncio.Task:

    def _session() -> AsyncSession:
        return AsyncSession(bind=bind, expire_on_commit=False)

    async def _execute() -> None:
        from app.wiring.services import build_workflow_service

        async with _session() as probe:
            claim = await probe.get(WorkflowRun, workflow_run_id)
            worker_id = claim.lease_owner if claim else None
            attempt = claim.attempt_count if claim else 0
            status = claim.status if claim else None
        if expected_lease_owner is not None and (status != "queued" or worker_id != expected_lease_owner):
            # The claim this resume was started for never committed, or was
            # taken over; whoever holds the run continues it.
            logger.info(
                f"{label} skipped: the run is not claimed for it",
                extra={"workflow_run_id": workflow_run_id},
            )
            return
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
                    log_label=f"{label} lease",
                ).run(stop, lease_lost)
            )
        try:
            async with _session() as exec_db:
                try:
                    service = build_workflow_service(db=exec_db, ctx=ctx)
                    await execute(service)
                except Exception:
                    # The engine already recorded the failure on the Run; the
                    # run stays a dead letter and can be redriven again.
                    logger.exception(
                        f"{label} failed",
                        extra={"workflow_run_id": workflow_run_id},
                    )
                finally:
                    # The engine leaves its final run transition uncommitted;
                    # closing without committing would roll the terminal
                    # status back and strand the run.
                    await exec_db.commit()
        finally:
            stop.set()
            if heartbeat is not None:
                await heartbeat

    task = asyncio.create_task(_execute())
    _redrive_tasks.add(task)
    task.add_done_callback(_redrive_tasks.discard)
    return task
