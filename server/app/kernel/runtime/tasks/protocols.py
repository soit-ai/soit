"""Task repository protocols."""

from __future__ import annotations

from typing import Protocol

from app.kernel.runtime.db.models.tasks import Task, TaskCheckpoint, TaskEvent


class TaskRepositoryProtocol(Protocol):
    """Task persistence contract used by runtime core services."""

    async def create_task(self, task: Task) -> Task: ...

    async def get_task(self, task_id: str) -> Task | None: ...

    async def update_task(self, task: Task, *, outbox_events: list[str] | None = None) -> Task: ...

    async def add_checkpoint(self, checkpoint: TaskCheckpoint) -> TaskCheckpoint: ...

    async def add_event(self, event: TaskEvent) -> TaskEvent: ...


__all__ = ["TaskRepositoryProtocol"]
