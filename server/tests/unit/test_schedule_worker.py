"""test_schedule_worker

The scheduler owns when, not how. These cover the claim, what a firing hands
off to, and the two policy decisions that make a scheduler predictable after an
outage: only one worker fires an occurrence, and a missed occurrence is skipped
unless somebody asked for it to be caught up.
"""

from datetime import timedelta

import pytest
from sqlmodel import select

from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.responses import ResponseInteraction
from app.kernel.runtime.db.models.schedules import Schedule
from app.kernel.runtime.schedules.service import ScheduleService
from app.wiring.schedule_worker import ScheduleWorker


def _service(async_db, ctx) -> ScheduleService:
    return ScheduleService(async_db, ctx)


def _factory(async_db):
    """A session factory that shares this test's in-memory database."""
    from sqlmodel.ext.asyncio.session import AsyncSession

    engine = async_db.bind
    return lambda: AsyncSession(bind=engine, expire_on_commit=False)


async def _due_schedule(async_db, ctx, **overrides) -> Schedule:
    fields = {
        "tenant_id": ctx.tenant_id,
        "workspace_id": ctx.workspace_id,
        "name": "hourly-audit",
        "target_kind": "agent",
        "target_id": "agt_audit",
        "input_json": {"input": "run the audit"},
        "cron": "0 * * * *",
        "timezone": "UTC",
        "enabled": True,
        "next_fire_at": utc_now() - timedelta(minutes=1),
    }
    fields.update(overrides)
    schedule = Schedule(**fields)
    async_db.add(schedule)
    await async_db.commit()
    await async_db.refresh(schedule)
    return schedule


def _aware(moment):
    """SQLite hands back naive timestamps; treat them as the UTC they are."""
    from datetime import UTC

    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


async def _interactions(async_db) -> list[ResponseInteraction]:
    rows = (await async_db.exec(select(ResponseInteraction))).all()
    return [row if hasattr(row, "id") else row[0] for row in rows]


@pytest.mark.asyncio
async def test_firing_an_agent_queues_work_rather_than_running_it(async_db, ctx):
    """The scheduler must not execute: a crash mid-run would lose the run."""
    schedule = await _due_schedule(async_db, ctx)
    worker = ScheduleWorker(_factory(async_db))

    fired = await worker.fire_once()

    assert fired == schedule.id
    queued = await _interactions(async_db)
    assert len(queued) == 1
    assert queued[0].status == "queued"
    job = queued[0].execution_json
    assert job["payload"]["agent_id"] == "agt_audit"
    # The run can be traced back to what started it.
    assert job["payload"]["metadata"]["schedule_id"] == schedule.id
    # And it is attributed to the schedule, not to whoever last edited it.
    assert queued[0].created_by == f"system:schedule:{schedule.id}"


@pytest.mark.asyncio
async def test_an_occurrence_fires_once_even_with_two_workers(async_db, ctx):
    await _due_schedule(async_db, ctx)
    first = ScheduleWorker(_factory(async_db), worker_id="worker-a")
    second = ScheduleWorker(_factory(async_db), worker_id="worker-b")

    assert await first.fire_once() is not None
    # The claim moved the next firing forward, so the second worker finds
    # nothing due.
    assert await second.fire_once() is None
    assert len(await _interactions(async_db)) == 1


@pytest.mark.asyncio
async def test_nothing_fires_before_it_is_due(async_db, ctx):
    await _due_schedule(async_db, ctx, next_fire_at=utc_now() + timedelta(hours=1))
    worker = ScheduleWorker(_factory(async_db))

    assert await worker.fire_once() is None
    assert await _interactions(async_db) == []


@pytest.mark.asyncio
async def test_a_paused_schedule_never_fires(async_db, ctx):
    await _due_schedule(async_db, ctx, enabled=False)
    worker = ScheduleWorker(_factory(async_db))

    assert await worker.fire_once() is None


@pytest.mark.asyncio
async def test_a_missed_occurrence_is_skipped_by_default(async_db, ctx):
    """An hourly job down for six hours resumes hourly, not six times at once."""
    long_overdue = utc_now() - timedelta(hours=6)
    schedule = await _due_schedule(async_db, ctx, next_fire_at=long_overdue, catch_up=False)
    worker = ScheduleWorker(_factory(async_db))

    await worker.fire_once()
    await async_db.refresh(schedule)

    assert _aware(schedule.next_fire_at) > utc_now()
    # One firing, not six.
    assert len(await _interactions(async_db)) == 1
    assert await worker.fire_once() is None


@pytest.mark.asyncio
async def test_catch_up_walks_the_missed_occurrences_one_at_a_time(async_db, ctx):
    """Asked for explicitly, and still one occurrence per pass."""
    long_overdue = utc_now() - timedelta(hours=3)
    schedule = await _due_schedule(async_db, ctx, next_fire_at=long_overdue, catch_up=True)
    worker = ScheduleWorker(_factory(async_db))

    await worker.fire_once()
    await async_db.refresh(schedule)

    # The next firing is the occurrence after the one just caught up, which is
    # still in the past, so the sweep keeps going rather than jumping to now.
    assert _aware(schedule.next_fire_at) < utc_now()
    assert await worker.fire_once() is not None


@pytest.mark.asyncio
async def test_a_target_that_cannot_run_is_recorded_and_retried_next_time(async_db, ctx):
    """A deleted workflow must not wedge the schedule."""
    schedule = await _due_schedule(async_db, ctx, target_kind="workflow", target_id="wf_missing")
    worker = ScheduleWorker(_factory(async_db))

    await worker.fire_once()
    await async_db.refresh(schedule)

    assert schedule.last_status == "failed"
    assert schedule.last_error
    # Still scheduled: one bad firing is not a reason to stop trying.
    assert schedule.enabled is True
    assert schedule.next_fire_at is not None


@pytest.mark.asyncio
async def test_a_manual_firing_leaves_the_next_occurrence_alone(async_db, ctx):
    """Asking for a run now is not the same as moving the schedule."""
    schedule = await _due_schedule(async_db, ctx, next_fire_at=utc_now() + timedelta(hours=1))
    before = schedule.next_fire_at
    worker = ScheduleWorker(_factory(async_db))

    await worker.fire_schedule(schedule, db=async_db, advance=False)
    await async_db.refresh(schedule)

    assert _aware(schedule.next_fire_at) == _aware(before)
    assert len(await _interactions(async_db)) == 1


@pytest.mark.asyncio
async def test_saving_an_expression_that_cannot_fire_is_refused(async_db, ctx):
    from app.kernel.commons.errors import ValidationError

    service = _service(async_db, ctx)

    with pytest.raises(ValidationError):
        await service.create(name="bad", target_kind="agent", target_id="a", cron="not a cron")
    with pytest.raises(ValidationError):
        await service.create(
            name="bad-zone",
            target_kind="agent",
            target_id="a",
            cron="0 * * * *",
            timezone="Nowhere/Special",
        )
    with pytest.raises(ValidationError):
        await service.create(name="bad-kind", target_kind="teapot", target_id="a", cron="0 * * * *")


@pytest.mark.asyncio
async def test_pausing_clears_the_next_firing_rather_than_leaving_a_stale_one(async_db, ctx):
    service = _service(async_db, ctx)
    schedule = await service.create(
        name="nightly", target_kind="agent", target_id="agt", cron="0 2 * * *"
    )
    assert schedule.next_fire_at is not None

    paused = await service.update(schedule.id, enabled=False)
    assert paused.next_fire_at is None

    resumed = await service.update(schedule.id, enabled=True)
    assert resumed.next_fire_at is not None
