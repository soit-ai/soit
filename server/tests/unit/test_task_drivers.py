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


@pytest.fixture(autouse=True)
def _isolated_registry():
    drivers.clear_task_drivers()
    yield
    drivers.clear_task_drivers()


def _failed_task(db, ctx: RequestContext, *, task_type: str = "agent.execute") -> Task:
    service = TaskService(db, ctx)
    task = service.create_task(task_type=task_type)
    task.status = TaskStatus.FAILED.value
    db.add(task)
    db.commit()
    db.refresh(task)
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


def test_registry_reports_only_registered_types():
    assert not drivers.is_drivable("agent.execute")

    drivers.register_task_driver("agent.execute", lambda _db, _task: None)

    assert drivers.is_drivable("agent.execute")
    assert drivers.registered_task_types() == frozenset({"agent.execute"})


def test_retry_is_rejected_when_no_driver_can_run_the_task(db, ctx):
    task = _failed_task(db, ctx)
    service = TaskService(db, ctx)

    with pytest.raises(ConflictError):
        service.retry_task(task_id=task.id)

    db.refresh(task)
    assert task.status == TaskStatus.FAILED.value


def test_retry_requeues_the_task_once_a_driver_exists(db, ctx):
    task = _failed_task(db, ctx)
    drivers.register_task_driver("agent.execute", lambda _db, _task: None)
    service = TaskService(db, ctx)

    retried = service.retry_task(task_id=task.id)

    assert retried.status == TaskStatus.QUEUED.value


def test_workbench_hides_retry_for_task_types_without_a_driver(db, ctx):
    task = _failed_task(db, ctx)
    query_service = TaskQueryService(db, ctx)

    assert query_service._available_actions(task) == []

    drivers.register_task_driver("agent.execute", lambda _db, _task: None)

    assert query_service._available_actions(task) == ["retry"]


def test_outbox_retry_invokes_the_registered_driver(db, ctx):
    task = _failed_task(db, ctx)
    task.status = TaskStatus.QUEUED.value
    db.add(task)
    db.commit()
    driven: list[str] = []
    drivers.register_task_driver(
        "agent.execute", lambda _db, driven_task: driven.append(driven_task.id)
    )

    handle_task_runtime_outbox(db, _retry_event(task))

    assert driven == [task.id]


def test_outbox_retry_fails_the_task_when_nothing_can_drive_it(db, ctx):
    task = _failed_task(db, ctx)
    task.status = TaskStatus.QUEUED.value
    db.add(task)
    db.commit()

    handle_task_runtime_outbox(db, _retry_event(task))

    db.refresh(task)
    # A queued task nothing can run would otherwise be reported as pending
    # forever; failing it keeps the workbench honest.
    assert task.status == TaskStatus.FAILED.value
    assert task.error_code == DRIVER_MISSING_ERROR_CODE
    assert task.finished_at is not None


def test_outbox_retry_ignores_tasks_that_already_moved_on(db, ctx):
    task = _failed_task(db, ctx)
    task.status = TaskStatus.RUNNING.value
    db.add(task)
    db.commit()
    driven: list[str] = []
    drivers.register_task_driver(
        "agent.execute", lambda _db, driven_task: driven.append(driven_task.id)
    )

    handle_task_runtime_outbox(db, _retry_event(task))

    db.refresh(task)
    assert driven == []
    assert task.status == TaskStatus.RUNNING.value


def test_outbox_ignores_non_retry_lifecycle_events(db, ctx):
    task = _failed_task(db, ctx)
    task.status = TaskStatus.QUEUED.value
    db.add(task)
    db.commit()
    event = _retry_event(task)
    event.event_type = TaskEventType.STARTED

    handle_task_runtime_outbox(db, event)

    db.refresh(task)
    assert task.status == TaskStatus.QUEUED.value
