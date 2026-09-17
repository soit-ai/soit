"""Task lifecycle facts are durable in task_events; only a retry reaches the outbox."""

from __future__ import annotations

import pytest
from sqlmodel import select

from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.status import TaskStatus
from app.kernel.runtime.tasks import drivers
from app.kernel.runtime.tasks.events import TaskEventType
from app.kernel.runtime.tasks.service import TaskService


async def _outbox_types(async_db, task_id: str) -> set[str]:
    rows = (await async_db.exec(select(EventOutbox).where(EventOutbox.task_id == task_id))).all()
    return {row.event_type for row in rows}


@pytest.mark.asyncio
async def test_task_lifecycle_is_recorded_in_task_events_not_on_the_outbox(async_db, tenant1_ctx) -> None:
    svc = TaskService(async_db, tenant1_ctx)
    task = await svc.create_task(task_type="agent_batch", input_payload={"batch_size": 1})
    await svc.transition_task(task_id=task.id, status=TaskStatus.RUNNING.value)
    await svc.add_checkpoint(task_id=task.id, checkpoint_no=1, status=TaskStatus.RUNNING.value)
    await svc.transition_task(task_id=task.id, status=TaskStatus.SUCCEEDED.value)

    timeline = [(event.event_type, event.payload_json.get("status")) for event in await svc.task_repo.list_events(task.id)]
    assert timeline == [
        ("task.created", TaskStatus.QUEUED.value),
        ("task.status", TaskStatus.RUNNING.value),
        ("task.checkpoint", TaskStatus.RUNNING.value),
        ("task.status", TaskStatus.SUCCEEDED.value),
    ]
    assert await _outbox_types(async_db, task.id) == set()


@pytest.mark.asyncio
async def test_a_failed_task_records_its_error_without_an_outbox_row(async_db, tenant1_ctx) -> None:
    svc = TaskService(async_db, tenant1_ctx)
    task = await svc.create_task(task_type="x", input_payload={})
    await svc.transition_task(
        task_id=task.id,
        status=TaskStatus.FAILED.value,
        error_code="E1",
        error_message="boom",
    )

    events = await svc.task_repo.list_events(task.id)
    assert events[-1].event_type == "task.status"
    assert events[-1].payload_json["status"] == TaskStatus.FAILED.value
    assert events[-1].payload_json["error_code"] == "E1"
    assert await _outbox_types(async_db, task.id) == set()


@pytest.mark.asyncio
async def test_only_a_retry_reaches_the_outbox(async_db, tenant1_ctx) -> None:
    async def _driver(db, task) -> None:  # noqa: ARG001
        return None

    drivers.register_task_driver("retryable", _driver)
    try:
        svc = TaskService(async_db, tenant1_ctx)
        task = await svc.create_task(task_type="retryable", input_payload={})
        await svc.transition_task(task_id=task.id, status=TaskStatus.FAILED.value, error_code="E1")

        await svc.retry_task(task_id=task.id)

        rows = (await async_db.exec(select(EventOutbox).where(EventOutbox.task_id == task.id))).all()
        assert [row.event_type for row in rows] == [TaskEventType.RETRIED]
        assert rows[0].payload_json["status"] == TaskStatus.RETRYING.value
    finally:
        drivers.clear_task_drivers()
