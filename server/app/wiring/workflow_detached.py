"""Workflow executions that outlive the request that started them.

The streaming endpoint claims a leased ``WorkflowRun`` and hands the plan to
a task that runs on its own session, so a client disconnecting does not
stop the run. Composition lives here because the task builds the workflow
service itself.
"""

import asyncio
import uuid
from datetime import timedelta

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.common import lease
from app.modules.workflow.domain.models import WorkflowRun
from app.settings.settings import settings
from app.wiring.services import build_workflow_service

_detached_workflow_tasks: set[asyncio.Task] = set()


async def claim_workflow_execution(
    db,
    ctx: RequestContext,
    *,
    run_id: str,
    workflow_id: str,
    inputs: dict,
) -> str:
    """Persist a leased WorkflowRun so the execution outlives this request."""
    lease_seconds = lease.normalize_lease_seconds(
        settings.workflow_execution_lease_seconds
    )
    claim = WorkflowRun(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id=run_id,
        workflow_id=workflow_id,
        status="running",
        inputs_json=dict(inputs or {}),
        request_context_json=ctx.to_json(),
        lease_owner=f"workflow-api-{uuid.uuid4()}",
        lease_expires_at=utc_now() + timedelta(seconds=lease_seconds),
        attempt_count=1,
    )
    db.add(claim)
    await db.commit()
    return claim.id


def start_detached_workflow_execution(
    *,
    bind,
    ctx: RequestContext,
    plan,
    claim_id: str,
) -> asyncio.Task:
    """Run the plan on an independent session, renewing the claim's lease.

    The task is tracked at module level so it keeps running after the SSE
    response is closed. Only process death ends it early, and then the lease
    expiry makes the orphan visible.
    """

    def _session() -> AsyncSession:
        return AsyncSession(bind=bind, expire_on_commit=False)

    async def _execute() -> None:
        async def service_engine_execute(exec_db) -> None:
            service = build_workflow_service(db=exec_db, ctx=ctx)
            await service.engine.execute(plan)

        claim = None
        async with _session() as probe:
            claim = await probe.get(WorkflowRun, claim_id)
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
                    claim_id,
                    worker_id=worker_id,
                    attempt_count=attempt,
                    lease_seconds=lease.normalize_lease_seconds(
                        settings.workflow_execution_lease_seconds
                    ),
                    log_label="Workflow execution lease",
                ).run(stop, lease_lost)
            )
        try:
            async with _session() as exec_db:
                try:
                    await service_engine_execute(exec_db)
                finally:
                    # The engine leaves its final run transition uncommitted
                    # (request sessions used to flush it during teardown).
                    # Closing without committing would roll the terminal
                    # status back and strand the run as "running".
                    await exec_db.commit()
        finally:
            stop.set()
            if heartbeat is not None:
                await heartbeat
            # The engine clears the lease on its terminal writes; a cancelled
            # or interrupted attempt may leave the claim running, in which
            # case the reaper resolves it once the lease lapses.

    task = asyncio.create_task(_execute())
    _detached_workflow_tasks.add(task)
    task.add_done_callback(_detached_workflow_tasks.discard)
    return task
