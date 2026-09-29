"""Registry of drivers that can re-execute a task.

Changing a task's status does not by itself make anything run again. A task
type is only retryable or resumable when something is registered here to drive
it; without a driver the task would sit in a non-terminal state forever while
the UI reported it as queued.

Kernel owns the registry, wiring registers the drivers, so module-level
execution code stays out of the kernel.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import KernelError
from app.kernel.runtime.db.models.tasks import Task

TaskDriver = Callable[[AsyncSession, Task], Awaitable[None]]
"""Re-drives one task. Responsible for moving it out of its queued state."""

TASK_NOT_RERUNNABLE_ERROR_CODE = "TASK_NOT_RERUNNABLE"
"""Error code of a retry refused because nothing re-executes the task type."""

_DRIVERS: dict[str, TaskDriver] = {}


def not_rerunnable_reason(task_type: str) -> str:
    """The reason a task of ``task_type`` cannot be re-run, for callers to record."""
    return f"No driver re-executes task type {task_type!r}"


class TaskNotRerunnableError(KernelError):
    """A retry was refused: no driver re-executes tasks of this type.

    This is a property of the task type, not a transient state: the task keeps
    its terminal status, and the response names the type so the caller can
    tell it apart from a task that is simply not finished yet.
    """

    def __init__(self, *, task_id: str, task_type: str) -> None:
        super().__init__(
            TASK_NOT_RERUNNABLE_ERROR_CODE,
            not_rerunnable_reason(task_type),
            {"task_id": task_id, "task_type": task_type, "reason": "task_not_rerunnable"},
        )


def register_task_driver(task_type: str, driver: TaskDriver) -> None:
    """Register the driver that re-executes tasks of ``task_type``."""
    _DRIVERS[task_type] = driver


def get_task_driver(task_type: str) -> TaskDriver | None:
    """Return the driver for ``task_type``, or None when it cannot be driven."""
    return _DRIVERS.get(task_type)


def is_drivable(task_type: str) -> bool:
    """Return whether re-execution of ``task_type`` is actually implemented."""
    return task_type in _DRIVERS


def registered_task_types() -> frozenset[str]:
    """Return every task type that can be re-driven."""
    return frozenset(_DRIVERS)


def clear_task_drivers() -> None:
    """Drop all registrations. Intended for tests and wiring rebuilds."""
    _DRIVERS.clear()
