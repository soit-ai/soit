"""Contracts for the workflow orphan reaper."""

from datetime import timedelta

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run
from app.modules.workflow.domain.models import WorkflowRun
from app.modules.workflow.runtime.reaper import (
    ORPHANED_ERROR_CODE,
    reap_orphaned_workflow_runs,
)


def _running_workflow(
    db,
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
    db.add(run)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_reaper_fails_runs_whose_lease_expired(db, ctx):
    orphan = _running_workflow(db, ctx, run_id="run_orphaned", lease_delta_minutes=-5)

    reaped = reap_orphaned_workflow_runs(db)

    db.refresh(orphan)
    run = db.get(Run, "run_orphaned")
    assert reaped == 1
    # An interrupted execution must become an honest failure, not report
    # "running" forever for work nothing will ever finish.
    assert orphan.status == "failed"
    assert orphan.lease_owner is None
    assert run.status == "failed"
    assert run.error_code == ORPHANED_ERROR_CODE
    assert run.ended_at is not None


def test_reaper_leaves_live_leases_alone(db, ctx):
    live = _running_workflow(db, ctx, run_id="run_live", lease_delta_minutes=10)

    reaped = reap_orphaned_workflow_runs(db)

    db.refresh(live)
    assert reaped == 0
    assert live.status == "running"
    assert live.lease_owner == "workflow-api-dead"


def test_reaper_does_not_override_a_terminal_trace_run(db, ctx):
    orphan = _running_workflow(db, ctx, run_id="run_already_done", lease_delta_minutes=-5)
    run = db.get(Run, "run_already_done")
    run.status = "canceled"
    db.add(run)
    db.commit()

    reap_orphaned_workflow_runs(db)

    db.refresh(orphan)
    db.refresh(run)
    # The aggregate row is closed out, but a run that already reached a
    # terminal state keeps its verdict.
    assert orphan.status == "failed"
    assert run.status == "canceled"
    assert run.error_code is None
