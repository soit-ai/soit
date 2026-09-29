"""Core runtime handling for task lifecycle outbox events."""

from __future__ import annotations

import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.status import TaskStatus
from app.kernel.runtime.tasks.drivers import (
    TASK_NOT_RERUNNABLE_ERROR_CODE,
    get_task_driver,
    not_rerunnable_reason,
)
from app.kernel.runtime.tasks.events import TaskEventType
from app.kernel.runtime.tasks.service import TaskService

logger = logging.getLogger(__name__)

RETRY_REFUSED_EVENT_TYPE = "task.retry_refused"
"""Task event recorded when a requeued task turns out to have no driver."""

_REDRIVABLE_STATUSES = frozenset(
    {TaskStatus.QUEUED.value, TaskStatus.RETRYING.value}
)

_TERMINAL_STATUSES = frozenset(
    {
        TaskStatus.FAILED.value,
        TaskStatus.CANCELED.value,
        TaskStatus.EXPIRED.value,
    }
)


def _system_context(task: Task) -> RequestContext:
    return RequestContext(
        tenant_id=task.tenant_id,
        workspace_id=task.workspace_id,
        user_id=task.created_by or "system",
        tenant_role="Owner",
        workspace_role="Owner",
    )


async def _refuse_retry(db: AsyncSession, task: Task) -> None:
    """Return a requeued task nothing can drive to the state the retry left.

    The retry records that state in the task's progress; a row requeued by
    a release that did not record it is treated as failed, the state most
    retries start from. Either way the task did not fail again: the reason
    is recorded as an event and as the task's error, and the terminal status
    is the previous one.
    """
    progress = dict(task.progress_json or {})
    retried_from = str(progress.get("retried_from") or "")
    restored = retried_from if retried_from in _TERMINAL_STATUSES else TaskStatus.FAILED.value
    reason = not_rerunnable_reason(task.task_type)
    logger.warning(
        "%s; task %s returns to %s",
        reason,
        task.id,
        restored,
        extra={"task_id": task.id, "task_type": task.task_type},
    )
    service = TaskService(db, _system_context(task))
    await service.add_task_event(
        task_id=task.id,
        event_type=RETRY_REFUSED_EVENT_TYPE,
        payload={
            "reason": "task_not_rerunnable",
            "task_type": task.task_type,
            "restored_status": restored,
        },
    )
    await service.transition_task(
        task_id=task.id,
        status=restored,
        progress={**progress, "action": "retry_refused"},
        error_code=TASK_NOT_RERUNNABLE_ERROR_CODE,
        error_message=reason,
    )


async def handle_task_runtime_outbox(db: AsyncSession, row: EventOutbox) -> None:
    """Re-drive a retried task, or fail it when nothing can run it.

    Only retries need core action here: every other lifecycle event already
    matches the task row, and separate handlers build observe projections.
    """
    if row.event_type != TaskEventType.RETRIED:
        return None

    task_id = row.task_id or str((row.payload_json or {}).get("task_id") or "")
    if not task_id:
        return None

    task = await db.get(Task, task_id)
    if task is None:
        return None
    if task.status not in _REDRIVABLE_STATUSES:
        # Something already moved the task on; re-driving would duplicate work.
        return None

    driver = get_task_driver(task.task_type)
    if driver is None:
        # The retry was accepted by a process that had a driver this one lacks,
        # or the row outlived the registration. Leaving the task queued would
        # strand it as pending forever; failing it would report a failure that
        # never happened. Put it back where the retry found it and say why.
        await _refuse_retry(db, task)
        return None

    await driver(db, task)
    return None
