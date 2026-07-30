"""Retrying an agent task replays its persisted interaction snapshot."""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.responses import ResponseInteraction
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.status import TaskStatus
from app.kernel.runtime.tasks import drivers
from app.kernel.runtime.tasks.service import TaskService
from app.wiring.task_drivers import (
    SNAPSHOT_MISSING_ERROR_CODE,
    drive_agent_task_retry,
    register_task_drivers,
)


@pytest.fixture(autouse=True)
def _drivers():
    drivers.clear_task_drivers()
    register_task_drivers()
    yield
    drivers.clear_task_drivers()


def _failed_agent_task(db: Session, ctx: RequestContext, *, run_id: str) -> Task:
    service = TaskService(db, ctx)
    task = service.create_task(
        task_type="agent.stream",
        agent_id="agt_retry",
        thread_id="thread_retry",
        run_id=run_id,
    )
    task.status = TaskStatus.QUEUED.value
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _snapshot(db: Session, ctx: RequestContext, *, run_id: str) -> ResponseInteraction:
    interaction = ResponseInteraction(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        interaction_id="rint_original",
        response_id="resp_original",
        run_id=run_id,
        thread_id="thread_retry",
        request_hash="hash_original",
        execution_json={
            "mode": "agent",
            "agent_id": "agt_retry",
            "agent_inputs": {"message": "hello"},
            "assistant_message_id": "thmsg_original",
            "payload": {"agent_id": "agt_retry", "task_id": "task_original"},
        },
        request_context_json={
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "user_id": ctx.user_id,
        },
        status="failed",
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    return interaction


def _queued_replays(db: Session) -> list[ResponseInteraction]:
    return list(
        db.execute(
            select(ResponseInteraction).where(ResponseInteraction.status == "queued")
        )
        .scalars()
        .all()
    )


def test_agent_stream_tasks_are_registered_as_retryable():
    assert drivers.is_drivable("agent.stream")


def test_retry_enqueues_a_replay_the_durable_worker_can_claim(db, ctx):
    task = _failed_agent_task(db, ctx, run_id="run_retry_replay")
    _snapshot(db, ctx, run_id="run_retry_replay")

    drive_agent_task_retry(db, task)

    replays = _queued_replays(db)
    assert len(replays) == 1
    replay = replays[0]
    assert replay.status == "queued"
    assert replay.thread_id == "thread_retry"
    assert replay.execution_json["mode"] == "agent"
    assert replay.execution_json["agent_inputs"] == {"message": "hello"}
    # A queued replay with no bound response is exactly what the worker claims;
    # a bound one would be terminalized as an orphan instead of executed.
    assert replay.response_id is None
    assert replay.run_id is None


def test_replay_does_not_reuse_the_previous_attempt_identifiers(db, ctx):
    task = _failed_agent_task(db, ctx, run_id="run_retry_ids")
    _snapshot(db, ctx, run_id="run_retry_ids")

    drive_agent_task_retry(db, task)

    replay = _queued_replays(db)[0]
    assert replay.interaction_id != "rint_original"
    assert replay.execution_json["assistant_message_id"] != "thmsg_original"
    assert "task_id" not in replay.execution_json["payload"]


def test_retried_task_is_closed_out_and_points_at_the_replay(db, ctx):
    task = _failed_agent_task(db, ctx, run_id="run_retry_closeout")
    _snapshot(db, ctx, run_id="run_retry_closeout")

    drive_agent_task_retry(db, task)

    db.refresh(task)
    replay = _queued_replays(db)[0]
    # Replaying creates a new run and task, so this attempt must reach a
    # terminal state instead of waiting for work it will never perform.
    assert task.status == TaskStatus.CANCELED.value
    assert task.finished_at is not None
    assert task.progress_json["retried_as_interaction_id"] == replay.interaction_id


def test_retry_fails_explicitly_when_no_snapshot_was_persisted(db, ctx):
    task = _failed_agent_task(db, ctx, run_id="run_retry_missing")

    drive_agent_task_retry(db, task)

    db.refresh(task)
    assert task.status == TaskStatus.FAILED.value
    assert task.error_code == SNAPSHOT_MISSING_ERROR_CODE
    assert _queued_replays(db) == []
