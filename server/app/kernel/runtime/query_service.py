"""Read-side services for runtime tasks."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.models import Task, Thread
from app.kernel.runtime.repository import TaskRepository, ThreadRepository


class RuntimeQueryService:
    """Read-only access to runtime task records."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx
        self.thread_repo = ThreadRepository(db, ctx)
        self.task_repo = TaskRepository(db, ctx)

    def list_threads(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> list[Thread]:
        return self.thread_repo.list_threads(
            limit=limit,
            offset=offset,
            status=status,
            agent_id=agent_id,
        )

    def get_thread(self, thread_id: str) -> Thread:
        thread = self.thread_repo.get_thread(thread_id)
        if not thread:
            raise NotFoundError(f"Thread not found: {thread_id}")
        return thread

    def list_thread_messages(self, thread_id: str):
        self.get_thread(thread_id)
        return self.thread_repo.list_messages(thread_id)

    def list_tasks(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        agent_id: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> list[Task]:
        return self.task_repo.list_tasks(
            limit=limit,
            offset=offset,
            status=status,
            task_type=task_type,
            agent_id=agent_id,
            thread_id=thread_id,
        )

    def get_task(self, task_id: str) -> Task:
        task = self.task_repo.get_task(task_id)
        if not task:
            raise NotFoundError(f"Task not found: {task_id}")
        return task

    def list_task_events(self, task_id: str):
        self.get_task(task_id)
        return self.task_repo.list_events(task_id)

    def list_task_checkpoints(self, task_id: str):
        self.get_task(task_id)
        return self.task_repo.list_checkpoints(task_id)
