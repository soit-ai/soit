"""test_pagination_totals

Covers the optional ``total`` on paginated list responses and the creation-time
window filters that the console counts depend on. A count is only computed when
the caller asks for it, so both paths are asserted: absent means "not
requested", never "zero rows".
"""

from datetime import timedelta

import pytest

from app.api.v1.run.handlers import RunHandlers
from app.api.v1.task.handlers import TaskHandlers
from app.kernel.commons.ids import generate_run_id
from app.kernel.commons.time import utc_now
from app.kernel.contracts.api import PaginatedResponse
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.db.models.runs import Run, RunStep
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.runs.service import RunService
from app.kernel.runtime.tasks.query_service import TaskQueryService


def _make_run(ctx, *, status: str = "succeeded", trace_id: str = "trace_total") -> Run:
    return Run(
        id=generate_run_id(),
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        trace_id=trace_id,
        mode="chat",
        kind="chat",
        subject_kind="agent",
        subject_id="agt_total",
        subject_version_id="app_v1",
        status=status,
        started_at=utc_now(),
    )


def test_paginated_response_total_is_absent_unless_supplied():
    """A response without a requested count carries no total at all."""
    without = PaginatedResponse.create(items=[1, 2], page_size=2)
    with_total = PaginatedResponse.create(items=[1, 2], page_size=2, total=7)

    assert without.total is None
    assert with_total.total == 7


@pytest.mark.asyncio
async def test_list_runs_total_counts_beyond_the_page(db, ctx):
    """The count covers every matching run, not just the page returned."""
    for _ in range(3):
        db.add(_make_run(ctx))
    db.commit()

    handlers = RunHandlers(RunService(db, ctx))

    without = await handlers.list_runs(ctx, subject_id="agt_total", page_size=2)
    assert without.total is None
    assert len(without.items) == 2

    counted = await handlers.list_runs(
        ctx,
        subject_id="agt_total",
        page_size=2,
        with_total=True,
    )
    assert len(counted.items) == 2
    assert counted.total == 3


@pytest.mark.asyncio
async def test_list_runs_total_respects_the_same_filters(db, ctx):
    """A filtered listing and its count agree on what matches."""
    db.add(_make_run(ctx, status="succeeded"))
    db.add(_make_run(ctx, status="failed"))
    db.commit()

    handlers = RunHandlers(RunService(db, ctx))

    counted = await handlers.list_runs(
        ctx,
        subject_id="agt_total",
        status="failed",
        page_size=50,
        with_total=True,
    )
    assert counted.total == 1
    assert len(counted.items) == 1


def test_count_runs_is_zero_when_an_observe_filter_excludes_everything(db, ctx):
    """A filter that cannot match anything counts zero without a query error."""
    db.add(_make_run(ctx))
    db.commit()

    service = RunService(db, ctx)
    assert service.count_runs(subject_id="agt_total") == 1
    assert service.count_runs(subject_id="agt_total", has_tool_call=True) == 0


@pytest.mark.asyncio
async def test_list_steps_total_counts_all_matching_steps(db, ctx):
    """Trace pages count spans across the whole trace, not the page."""
    run = _make_run(ctx, trace_id="trace_steps")
    db.add(run)
    db.commit()
    for index in range(3):
        db.add(
            RunStep(
                id=f"step_total_{index}",
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                run_id=run.id,
                trace_id="trace_steps",
                step_type="llm",
                status="succeeded",
                node_id=f"node_{index}",
                started_at=utc_now(),
            )
        )
    db.commit()

    handlers = RunHandlers(RunService(db, ctx))
    counted = await handlers.list_steps(
        ctx,
        trace_id="trace_steps",
        page_size=2,
        with_total=True,
    )

    assert len(counted.items) == 2
    assert counted.total == 3


@pytest.mark.asyncio
async def test_list_audits_window_filters_and_counts(db, ctx):
    """Audits accept a creation window, and the count honours it."""
    now = utc_now()
    run = _make_run(ctx, trace_id="trace_audit")
    db.add(run)
    db.commit()
    for age_hours in (1, 48):
        db.add(
            AuditEvent(
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                event_type="tool.call",
                resource_type="tool",
                resource_id="tool_total",
                run_id=run.id,
                operation="invoke",
                outcome="allow",
                created_at=now - timedelta(hours=age_hours),
            )
        )
    db.commit()

    handlers = RunHandlers(RunService(db, ctx))

    all_audits = await handlers.list_audits(ctx, page_size=50, with_total=True)
    assert all_audits.total == 2

    last_day = await handlers.list_audits(
        ctx,
        since=now - timedelta(hours=24),
        page_size=50,
        with_total=True,
    )
    assert last_day.total == 1
    assert len(last_day.items) == 1

    nothing_yet = await handlers.list_audits(
        ctx,
        since=now + timedelta(hours=1),
        page_size=50,
        with_total=True,
    )
    assert nothing_yet.total == 0
    assert nothing_yet.items == []


@pytest.mark.asyncio
async def test_list_tasks_window_filters_and_counts(db, ctx):
    """Tasks accept the same creation window and report a total."""
    now = utc_now()
    for age_hours in (2, 72):
        db.add(
            Task(
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                task_type="agent.execute",
                status="queued",
                created_at=now - timedelta(hours=age_hours),
            )
        )
    db.commit()

    handlers = TaskHandlers(TaskQueryService(db, ctx))

    without = await handlers.list_tasks(
        ctx,
        status=None,
        task_type=None,
        agent_id=None,
        thread_id=None,
        page_token=None,
        page_size=20,
    )
    assert without.total is None

    last_day = await handlers.list_tasks(
        ctx,
        status=None,
        task_type=None,
        agent_id=None,
        thread_id=None,
        page_token=None,
        page_size=20,
        since=now - timedelta(hours=24),
        with_total=True,
    )
    assert last_day.total == 1
    assert len(last_day.items) == 1


@pytest.mark.asyncio
async def test_run_window_summary_counts_outcomes_and_spend(db, ctx):
    """The window summary counts every run, not a sampled page."""
    now = utc_now()
    for status in ("succeeded", "succeeded", "failed", "running"):
        db.add(_make_run(ctx, status=status))
    db.commit()

    handlers = RunHandlers(RunService(db, ctx))
    summary = await handlers.summarize_run_window(ctx, since=now - timedelta(hours=1))

    assert summary.total == 4
    assert summary.succeeded == 2
    assert summary.failed == 1
    assert summary.running == 1
    # Two of three settled runs passed; the in-flight one is not counted either way.
    assert summary.pass_rate == pytest.approx(2 / 3)


@pytest.mark.asyncio
async def test_run_window_pass_rate_is_absent_before_anything_settles(db, ctx):
    """A window with nothing finished reports no rate rather than zero."""
    db.add(_make_run(ctx, status="running"))
    db.commit()

    handlers = RunHandlers(RunService(db, ctx))
    summary = await handlers.summarize_run_window(ctx)

    assert summary.total == 1
    assert summary.pass_rate is None
