"""Contracts for the workflow orphan reaper."""

from datetime import timedelta

import pytest

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run
from app.modules.workflow.domain.models import WorkflowRun
from app.modules.workflow.runtime.reaper import (
    ORPHANED_ERROR_CODE,
    reap_orphaned_workflow_runs,
)


async def _running_workflow(
    async_db,
    ctx: RequestContext,
    *,
    run_id: str,
    lease_delta_minutes: int,
) -> WorkflowRun:
    run = Run(
        id=run_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        trace_id=f"tr_{run_id}",
        mode="workflow",
        kind="workflow",
        status="running",
    )
    row = WorkflowRun(
        id=f"wfr_{run_id}",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id=run_id,
        workflow_id="wf_reaper",
        status="running",
        lease_owner="workflow-api-dead",
        lease_expires_at=utc_now() + timedelta(minutes=lease_delta_minutes),
        attempt_count=1,
    )
    async_db.add(run)
    async_db.add(row)
    await async_db.commit()
    await async_db.refresh(row)
    return row


@pytest.mark.asyncio
async def test_reaper_fails_runs_whose_lease_expired(async_db, ctx):
    orphan = await _running_workflow(async_db, ctx, run_id="run_orphaned", lease_delta_minutes=-5)

    reaped = await reap_orphaned_workflow_runs(async_db)

    await async_db.refresh(orphan)
    run = await async_db.get(Run, "run_orphaned")
    assert reaped == 1
    # An interrupted execution must become an honest failure, not report
    # "running" forever for work nothing will ever finish.
    assert orphan.status == "failed"
    assert orphan.lease_owner is None
    assert run.status == "failed"
    assert run.error_code == ORPHANED_ERROR_CODE
    assert run.ended_at is not None


@pytest.mark.asyncio
async def test_reaper_leaves_live_leases_alone(async_db, ctx):
    live = await _running_workflow(async_db, ctx, run_id="run_live", lease_delta_minutes=10)

    reaped = await reap_orphaned_workflow_runs(async_db)

    await async_db.refresh(live)
    assert reaped == 0
    assert live.status == "running"
    assert live.lease_owner == "workflow-api-dead"


@pytest.mark.asyncio
async def test_reaper_does_not_override_a_terminal_trace_run(async_db, ctx):
    orphan = await _running_workflow(async_db, ctx, run_id="run_already_done", lease_delta_minutes=-5)
    run = await async_db.get(Run, "run_already_done")
    run.status = "canceled"
    async_db.add(run)
    await async_db.commit()

    await reap_orphaned_workflow_runs(async_db)

    await async_db.refresh(orphan)
    await async_db.refresh(run)
    # The aggregate row is closed out, but a run that already reached a
    # terminal state keeps its verdict.
    assert orphan.status == "failed"
    assert run.status == "canceled"
    assert run.error_code is None
