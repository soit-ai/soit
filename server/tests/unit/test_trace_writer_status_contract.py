"""TraceWriter lifecycle contract tests."""

from __future__ import annotations

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.runtime.db.models.runs import Run, RunStep
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.status import RuntimeTransitionError

pytestmark = pytest.mark.asyncio


async def test_run_terminal_status_cannot_be_overwritten(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run("agent")
    await writer.update_run_status(run.id, "running")
    await writer.update_run_status(run.id, "succeeded")

    with pytest.raises(RuntimeTransitionError, match="Invalid run transition"):
        await writer.update_run_status(run.id, "failed")

    await async_db.refresh(run)
    assert run.status == "succeeded"


async def test_run_same_terminal_status_is_idempotent(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run("agent")
    await writer.update_run_status(run.id, "running")
    first = await writer.update_run_status(run.id, "succeeded", output_summary="done")
    ended_at = first.ended_at

    second = await writer.update_run_status(run.id, "succeeded", output_summary="done")

    assert second.status == "succeeded"
    assert second.ended_at == ended_at


async def test_step_terminal_status_cannot_be_overwritten(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run("workflow")
    step = await writer.create_step(run.id, "tool")
    await writer.update_step_status(step.id, "running")
    await writer.update_step_status(step.id, "succeeded")

    with pytest.raises(RuntimeTransitionError, match="Invalid step transition"):
        await writer.update_step_status(step.id, "failed")

    await async_db.refresh(step)
    assert step.status == "succeeded"


async def test_unknown_runtime_status_is_rejected_without_mutation(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run("agent")

    with pytest.raises(RuntimeTransitionError, match="Unknown run status"):
        await writer.update_run_status(run.id, "completed")

    stored = await async_db.get(Run, run.id)
    assert stored is not None
    assert stored.status == "queued"


async def test_step_skipped_is_terminal(async_db, ctx):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run("workflow")
    step = await writer.create_step(run.id, "condition")

    skipped = await writer.update_step_status(step.id, "skipped")

    assert skipped.status == "skipped"
    assert skipped.ended_at is not None
    stored = await async_db.get(RunStep, step.id)
    assert stored is not None
    assert stored.status == "skipped"


async def test_stale_writer_cannot_win_terminal_status_race(async_db, ctx):
    initial_writer = TraceWriter(async_db, ctx)
    run = await initial_writer.create_run("agent")
    await initial_writer.update_run_status(run.id, "running")
    await async_db.commit()

    winner_session = AsyncSession(async_db.bind, expire_on_commit=False)
    stale_session = AsyncSession(async_db.bind, expire_on_commit=False)
    try:
        assert (await winner_session.get(Run, run.id)).status == "running"
        assert (await stale_session.get(Run, run.id)).status == "running"

        await TraceWriter(winner_session, ctx).update_run_status(run.id, "succeeded")
        await winner_session.commit()

        with pytest.raises(RuntimeTransitionError, match="Invalid run transition"):
            await TraceWriter(stale_session, ctx).update_run_status(run.id, "failed")
    finally:
        await winner_session.close()
        await stale_session.close()
