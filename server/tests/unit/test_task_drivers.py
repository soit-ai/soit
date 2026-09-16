"""Contracts for task re-execution drivers and retry outbox handling."""

import pytest

from app.kernel.commons.errors import ConflictError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.status import TaskStatus
from app.kernel.runtime.tasks import drivers
from app.kernel.runtime.tasks.events import TaskEventType
from app.kernel.runtime.tasks.on_task_outbox import (
    DRIVER_MISSING_ERROR_CODE,
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


async def _failed_task(db, ctx: RequestContext, *, task_type: str = "agent.execute") -> Task:
    service = TaskService(db, ctx)
    task = await service.create_task(task_type=task_type)
    task.status = TaskStatus.FAILED.value
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


async def test_retry_is_rejected_when_no_driver_can_run_the_task(async_db, ctx):
    task = await _failed_task(async_db, ctx)
    service = TaskService(async_db, ctx)

    with pytest.raises(ConflictError):
        await service.retry_task(task_id=task.id)

    await async_db.refresh(task)
    assert task.status == TaskStatus.FAILED.value


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


async def test_outbox_retry_fails_the_task_when_nothing_can_drive_it(async_db, ctx):
    task = await _failed_task(async_db, ctx)
    task.status = TaskStatus.QUEUED.value
    async_db.add(task)
    await async_db.commit()

    await handle_task_runtime_outbox(async_db, _retry_event(task))

    await async_db.refresh(task)
    # A queued task nothing can run would otherwise be reported as pending
    # forever; failing it keeps the workbench honest.
    assert task.status == TaskStatus.FAILED.value
    assert task.error_code == DRIVER_MISSING_ERROR_CODE
    assert task.finished_at is not None


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
