"""Retrying an agent task replays its persisted interaction snapshot."""

from __future__ import annotations

import pytest
from sqlmodel import select

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


async def _failed_agent_task(async_db, ctx: RequestContext, *, run_id: str) -> Task:
    service = TaskService(async_db, ctx)
    task = await service.create_task(
        task_type="agent.stream",
        agent_id="agt_retry",
        thread_id="thread_retry",
        run_id=run_id,
    )
    task.status = TaskStatus.QUEUED.value
    async_db.add(task)
    await async_db.commit()
    await async_db.refresh(task)
    return task


async def _snapshot(async_db, ctx: RequestContext, *, run_id: str) -> ResponseInteraction:
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
    async_db.add(interaction)
    await async_db.commit()
    await async_db.refresh(interaction)
    return interaction


async def _queued_replays(async_db) -> list[ResponseInteraction]:
    return list(
        (await async_db.execute(
            select(ResponseInteraction).where(ResponseInteraction.status == "queued")
        ))
        .scalars()
        .all()
    )


def test_agent_stream_tasks_are_registered_as_retryable():
    assert drivers.is_drivable("agent.stream")


def test_agent_execute_tasks_are_registered_as_retryable():
    assert drivers.is_drivable("agent.execute")


@pytest.mark.asyncio
async def test_retry_replays_an_inline_execute_snapshot(async_db, ctx):
    """The non-streaming path persists an "inline" snapshot; retry replays it."""
    service = TaskService(async_db, ctx)
    task = await service.create_task(
        task_type="agent.execute",
        agent_id="agt_retry",
        thread_id="thread_retry",
        run_id="run_inline_retry",
    )
    task.status = TaskStatus.QUEUED.value
    async_db.add(task)
    await async_db.commit()
    await async_db.refresh(task)
    interaction = ResponseInteraction(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        interaction_id="rint_inline",
        response_id=None,
        run_id="run_inline_retry",
        thread_id="thread_retry",
        request_hash="rint_inline",
        execution_json={
            "mode": "agent",
            "agent_id": "agt_retry",
            "agent_inputs": {"input": "run the task"},
            "assistant_message_id": "thmsg_inline",
        },
        request_context_json={
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "user_id": ctx.user_id,
        },
        # A crash mid-inline-execution leaves the snapshot in this state; it
        # must still be replayable.
        status="inline",
    )
    async_db.add(interaction)
    await async_db.commit()

    await drive_agent_task_retry(async_db, task)

    replays = await _queued_replays(async_db)
    assert len(replays) == 1
    replay = replays[0]
    assert replay.execution_json["agent_inputs"] == {"input": "run the task"}
    assert replay.execution_json["assistant_message_id"] != "thmsg_inline"
    assert replay.response_id is None
    await async_db.refresh(task)
    assert task.status == TaskStatus.CANCELED.value
    assert task.progress_json["retried_as_interaction_id"] == replay.interaction_id


@pytest.mark.asyncio
async def test_retry_enqueues_a_replay_the_durable_worker_can_claim(async_db, ctx):
    task = await _failed_agent_task(async_db, ctx, run_id="run_retry_replay")
    await _snapshot(async_db, ctx, run_id="run_retry_replay")

    await drive_agent_task_retry(async_db, task)

    replays = await _queued_replays(async_db)
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


@pytest.mark.asyncio
async def test_replay_does_not_reuse_the_previous_attempt_identifiers(async_db, ctx):
    task = await _failed_agent_task(async_db, ctx, run_id="run_retry_ids")
    await _snapshot(async_db, ctx, run_id="run_retry_ids")

    await drive_agent_task_retry(async_db, task)

    replay = (await _queued_replays(async_db))[0]
    assert replay.interaction_id != "rint_original"
    assert replay.execution_json["assistant_message_id"] != "thmsg_original"
    assert "task_id" not in replay.execution_json["payload"]


@pytest.mark.asyncio
async def test_retried_task_is_closed_out_and_points_at_the_replay(async_db, ctx):
    task = await _failed_agent_task(async_db, ctx, run_id="run_retry_closeout")
    await _snapshot(async_db, ctx, run_id="run_retry_closeout")

    await drive_agent_task_retry(async_db, task)

    await async_db.refresh(task)
    replay = (await _queued_replays(async_db))[0]
    # Replaying creates a new run and task, so this attempt must reach a
    # terminal state instead of waiting for work it will never perform.
    assert task.status == TaskStatus.CANCELED.value
    assert task.finished_at is not None
    assert task.progress_json["retried_as_interaction_id"] == replay.interaction_id


@pytest.mark.asyncio
async def test_retry_fails_explicitly_when_no_snapshot_was_persisted(async_db, ctx):
    task = await _failed_agent_task(async_db, ctx, run_id="run_retry_missing")

    await drive_agent_task_retry(async_db, task)

    await async_db.refresh(task)
    assert task.status == TaskStatus.FAILED.value
    assert task.error_code == SNAPSHOT_MISSING_ERROR_CODE
    assert await _queued_replays(async_db) == []
