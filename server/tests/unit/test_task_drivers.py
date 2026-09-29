"""Contracts for task re-execution drivers and retry outbox handling."""

import pytest

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.status import TaskStatus
from app.kernel.runtime.tasks import drivers
from app.kernel.runtime.tasks.drivers import (
    TASK_NOT_RERUNNABLE_ERROR_CODE,
    TaskNotRerunnableError,
)
from app.kernel.runtime.tasks.events import TaskEventType
from app.kernel.runtime.tasks.on_task_outbox import (
    RETRY_REFUSED_EVENT_TYPE,
    handle_task_runtime_outbox,
)
from app.kernel.runtime.tasks.query_service import TaskQueryService
from app.kernel.runtime.tasks.service import TaskService

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _isolated_registry():
    drivers.clear_task_drivers()
    yield
    drivers.clear_task_drivers()


async def _noop_driver(_db, _task) -> None:
    return None


async def _failed_task(
    db,
    ctx: RequestContext,
    *,
    task_type: str = "agent.execute",
    status: str = TaskStatus.FAILED.value,
) -> Task:
    service = TaskService(db, ctx)
    task = await service.create_task(task_type=task_type)
    task.status = status
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


def _retry_event(task: Task) -> EventOutbox:
    return EventOutbox(
        id=f"outbox_{task.id}",
        event_id=f"evt_task_retried_{task.id}",
        event_type=TaskEventType.RETRIED,
        tenant_id=task.tenant_id,
        workspace_id=task.workspace_id,
        idempotency_key=f"idem_{task.id}",
        task_id=task.id,
        payload_json={"task_id": task.id, "task_type": task.task_type},
    )


async def test_registry_reports_only_registered_types():
    assert not drivers.is_drivable("agent.execute")

    drivers.register_task_driver("agent.execute", _noop_driver)

    assert drivers.is_drivable("agent.execute")
    assert drivers.registered_task_types() == frozenset({"agent.execute"})


async def test_retry_is_refused_with_the_task_type_when_nothing_can_run_it(async_db, ctx):
    task = await _failed_task(async_db, ctx, task_type="wf_step")
    service = TaskService(async_db, ctx)

    with pytest.raises(TaskNotRerunnableError) as refused:
        await service.retry_task(task_id=task.id)

    # The refusal is typed and names the type, so a caller can tell it from
    # a task that is merely not finished yet.
    assert refused.value.code == TASK_NOT_RERUNNABLE_ERROR_CODE
    assert refused.value.details == {
        "task_id": task.id,
        "task_type": "wf_step",
        "reason": "task_not_rerunnable",
    }
    await async_db.refresh(task)
    assert task.status == TaskStatus.FAILED.value
    assert task.error_code is None


async def test_retry_records_the_status_it_left(async_db, ctx):
    task = await _failed_task(async_db, ctx, status=TaskStatus.CANCELED.value)
    drivers.register_task_driver("agent.execute", _noop_driver)

    retried = await TaskService(async_db, ctx).retry_task(task_id=task.id)

    assert retried.status == TaskStatus.QUEUED.value
    assert retried.progress_json == {"action": "requeued", "retried_from": "canceled"}


async def test_retry_requeues_the_task_once_a_driver_exists(async_db, ctx):
    task = await _failed_task(async_db, ctx)
    drivers.register_task_driver("agent.execute", _noop_driver)
    service = TaskService(async_db, ctx)

    retried = await service.retry_task(task_id=task.id)

    assert retried.status == TaskStatus.QUEUED.value


async def test_workbench_hides_retry_for_task_types_without_a_driver(async_db, ctx):
    task = await _failed_task(async_db, ctx)
    query_service = TaskQueryService(async_db, ctx)

    assert query_service._available_actions(task) == []

    drivers.register_task_driver("agent.execute", _noop_driver)

    assert query_service._available_actions(task) == ["retry"]


async def test_outbox_retry_invokes_the_registered_driver(async_db, ctx):
    task = await _failed_task(async_db, ctx)
    task.status = TaskStatus.QUEUED.value
    async_db.add(task)
    await async_db.commit()
    driven: list[str] = []

    async def _record(_db, driven_task) -> None:
        driven.append(driven_task.id)

    drivers.register_task_driver("agent.execute", _record)

    await handle_task_runtime_outbox(async_db, _retry_event(task))

    assert driven == [task.id]


async def test_outbox_retry_without_a_driver_returns_the_task_where_the_retry_found_it(
    async_db, ctx
):
    task = await _failed_task(async_db, ctx, status=TaskStatus.CANCELED.value)
    # The retry was accepted by a process that had a driver; this one lacks it.
    drivers.register_task_driver("agent.execute", _noop_driver)
    await TaskService(async_db, ctx).retry_task(task_id=task.id)
    drivers.clear_task_drivers()

    await handle_task_runtime_outbox(async_db, _retry_event(task))

    await async_db.refresh(task)
    # Leaving it queued would report work that never completes; failing it
    # would report a failure that never happened. It goes back to canceled,
    # with the reason on the task and in its events.
    assert task.status == TaskStatus.CANCELED.value
    assert task.error_code == TASK_NOT_RERUNNABLE_ERROR_CODE
    assert task.error_message == "No driver re-executes task type 'agent.execute'"
    assert task.finished_at is not None
    assert task.progress_json["action"] == "retry_refused"
    events = await TaskService(async_db, ctx).task_repo.list_events(task.id)
    refused = [event for event in events if event.event_type == RETRY_REFUSED_EVENT_TYPE]
    assert [event.payload_json for event in refused] == [
        {
            "reason": "task_not_rerunnable",
            "task_type": "agent.execute",
            "restored_status": "canceled",
        }
    ]
    assert events[-1].event_type == "task.status"
    assert events[-1].payload_json["status"] == TaskStatus.CANCELED.value


async def test_outbox_retry_without_a_driver_treats_an_unrecorded_origin_as_failed(async_db, ctx):
    task = await _failed_task(async_db, ctx, status=TaskStatus.QUEUED.value)

    await handle_task_runtime_outbox(async_db, _retry_event(task))

    await async_db.refresh(task)
    assert task.status == TaskStatus.FAILED.value
    assert task.error_code == TASK_NOT_RERUNNABLE_ERROR_CODE


async def test_outbox_retry_ignores_tasks_that_already_moved_on(async_db, ctx):
    task = await _failed_task(async_db, ctx)
    task.status = TaskStatus.RUNNING.value
    async_db.add(task)
    await async_db.commit()
    driven: list[str] = []

    async def _record(_db, driven_task) -> None:
        driven.append(driven_task.id)

    drivers.register_task_driver("agent.execute", _record)

    await handle_task_runtime_outbox(async_db, _retry_event(task))

    await async_db.refresh(task)
    assert driven == []
    assert task.status == TaskStatus.RUNNING.value


async def test_outbox_ignores_non_retry_lifecycle_events(async_db, ctx):
    task = await _failed_task(async_db, ctx)
    task.status = TaskStatus.QUEUED.value
    async_db.add(task)
    await async_db.commit()
    event = _retry_event(task)
    event.event_type = TaskEventType.STARTED

    await handle_task_runtime_outbox(async_db, event)

    await async_db.refresh(task)
    assert task.status == TaskStatus.QUEUED.value
