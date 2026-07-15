"""TraceWriter lifecycle contract tests."""

from __future__ import annotations

import pytest
from sqlmodel import Session

from app.kernel.runtime.db.models.runs import Run, RunStep
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.status import RuntimeTransitionError


def test_run_terminal_status_cannot_be_overwritten(db, ctx):
    writer = TraceWriter(db, ctx)
    run = writer.create_run("agent")
    writer.update_run_status(run.id, "running")
    writer.update_run_status(run.id, "succeeded")

    with pytest.raises(RuntimeTransitionError, match="Invalid run transition"):
        writer.update_run_status(run.id, "failed")

    db.refresh(run)
    assert run.status == "succeeded"


def test_run_same_terminal_status_is_idempotent(db, ctx):
    writer = TraceWriter(db, ctx)
    run = writer.create_run("agent")
    writer.update_run_status(run.id, "running")
    first = writer.update_run_status(run.id, "succeeded", output_summary="done")
    ended_at = first.ended_at

    second = writer.update_run_status(run.id, "succeeded", output_summary="done")

    assert second.status == "succeeded"
    assert second.ended_at == ended_at


def test_step_terminal_status_cannot_be_overwritten(db, ctx):
    writer = TraceWriter(db, ctx)
    run = writer.create_run("workflow")
    step = writer.create_step(run.id, "tool")
    writer.update_step_status(step.id, "running")
    writer.update_step_status(step.id, "succeeded")

    with pytest.raises(RuntimeTransitionError, match="Invalid step transition"):
        writer.update_step_status(step.id, "failed")

    db.refresh(step)
    assert step.status == "succeeded"


def test_unknown_runtime_status_is_rejected_without_mutation(db, ctx):
    writer = TraceWriter(db, ctx)
    run = writer.create_run("agent")

    with pytest.raises(RuntimeTransitionError, match="Unknown run status"):
        writer.update_run_status(run.id, "completed")

    stored = db.get(Run, run.id)
    assert stored is not None
    assert stored.status == "queued"


def test_step_skipped_is_terminal(db, ctx):
    writer = TraceWriter(db, ctx)
    run = writer.create_run("workflow")
    step = writer.create_step(run.id, "condition")

    skipped = writer.update_step_status(step.id, "skipped")

    assert skipped.status == "skipped"
    assert skipped.ended_at is not None
    assert db.get(RunStep, step.id).status == "skipped"


def test_stale_writer_cannot_win_terminal_status_race(db, ctx):
    initial_writer = TraceWriter(db, ctx)
    run = initial_writer.create_run("agent")
    initial_writer.update_run_status(run.id, "running")
    db.commit()

    winner_session = Session(db.get_bind())
    stale_session = Session(db.get_bind())
    try:
        assert winner_session.get(Run, run.id).status == "running"
        assert stale_session.get(Run, run.id).status == "running"

        TraceWriter(winner_session, ctx).update_run_status(run.id, "succeeded")
        winner_session.commit()

        with pytest.raises(RuntimeTransitionError, match="Invalid run transition"):
            TraceWriter(stale_session, ctx).update_run_status(run.id, "failed")
    finally:
        winner_session.close()
        stale_session.close()
