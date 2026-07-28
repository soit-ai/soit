"""Registry of drivers that can re-execute a task.

Changing a task's status does not by itself make anything run again. A task
type is only retryable or resumable when something is registered here to drive
it; without a driver the task would sit in a non-terminal state forever while
the UI reported it as queued.

Kernel owns the registry, wiring registers the drivers, so module-level
execution code stays out of the kernel.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.kernel.runtime.db.models.tasks import Task

TaskDriver = Callable[[Session, Task], None]
"""Re-drives one task. Responsible for moving it out of its queued state."""

_DRIVERS: dict[str, TaskDriver] = {}


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
