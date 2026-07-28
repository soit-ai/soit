"""Core runtime handling for task lifecycle outbox events."""

from __future__ import annotations

import logging

from sqlmodel import Session

from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.status import TaskStatus
from app.kernel.runtime.tasks.drivers import get_task_driver
from app.kernel.runtime.tasks.events import TaskEventType

logger = logging.getLogger(__name__)

DRIVER_MISSING_ERROR_CODE = "TASK_TYPE_NOT_DRIVABLE"

_REDRIVABLE_STATUSES = frozenset(
    {TaskStatus.QUEUED.value, TaskStatus.RETRYING.value}
)


def handle_task_runtime_outbox(db: Session, row: EventOutbox) -> None:
    """Re-drive a retried task, or fail it when nothing can run it.

    Only retries need core action here: every other lifecycle event already
    matches the task row, and separate handlers build observe projections.
    """
    if row.event_type != TaskEventType.RETRIED:
        return None

    task_id = row.task_id or str((row.payload_json or {}).get("task_id") or "")
    if not task_id:
        return None

    task = db.get(Task, task_id)
    if task is None:
        return None
    if task.status not in _REDRIVABLE_STATUSES:
        # Something already moved the task on; re-driving would duplicate work.
        return None

    driver = get_task_driver(task.task_type)
    if driver is None:
        # Leaving the task queued would strand it in a non-terminal state that
        # the workbench reports as pending forever. Fail it so the state is
        # honest and the operator sees why.
        logger.warning(
            "No driver registered to re-execute task type %s",
            task.task_type,
            extra={"task_id": task.id},
        )
        now = utc_now()
        task.status = TaskStatus.FAILED.value
        task.error_code = DRIVER_MISSING_ERROR_CODE
        task.error_message = (
            f"Re-execution of task type {task.task_type!r} is not implemented"
        )
        task.finished_at = now
        task.updated_at = now
        db.add(task)
        db.commit()
        return None

    driver(db, task)
    return None
