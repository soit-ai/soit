"""Task repositories."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.tasks import Task, TaskCheckpoint, TaskEvent
from app.kernel.runtime.tasks.events import TaskEventType
from app.kernel.runtime.tasks.outbox_emit import (
    enqueue_task_checkpoint_outbox,
    enqueue_task_outbox_event,
)


class TaskRepository:
    """Repository for runtime tasks, checkpoints, and task events."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def _count_value(self, result) -> int:
        if result is None:
            return 0
        try:
            return int(result[0] or 0)
        except (KeyError, TypeError, IndexError):
            return int(result or 0)

    def create_task(
        self,
        task: Task,
        *,
        outbox_events: Sequence[str] | None = None,
    ) -> Task:
        task.tenant_id = self.ctx.tenant_id
        task.workspace_id = self.ctx.workspace_id
        task.created_by = self.ctx.user_id
        task.updated_by = self.ctx.user_id
        self.db.add(task)
        self.db.flush()
        events = list(outbox_events) if outbox_events is not None else [TaskEventType.CREATED]
        for et in events:
            enqueue_task_outbox_event(self.db, self.ctx, event_type=et, task=task)
        self.db.flush()
        self.db.refresh(task)
        return task

    def get_task(self, task_id: str) -> Task | None:
        query = select(Task).where(
            and_(
                Task.id == task_id,
                Task.tenant_id == self.ctx.tenant_id,
                Task.workspace_id == self.ctx.workspace_id,
            )
        )
        result = self.db.exec(query).first()
        return result if isinstance(result, Task) else result[0] if result else None

    def list_tasks(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
        task_type: str | None = None,
        agent_id: str | None = None,
        thread_id: str | None = None,
    ) -> list[Task]:
        filters = [
            Task.tenant_id == self.ctx.tenant_id,
            Task.workspace_id == self.ctx.workspace_id,
        ]
        if status:
            filters.append(Task.status == status)
        if task_type:
            filters.append(Task.task_type == task_type)
        if agent_id:
            filters.append(Task.agent_id == agent_id)
        if thread_id:
            filters.append(Task.thread_id == thread_id)

        query = (
            select(Task)
            .where(and_(*filters))
            .order_by(desc(Task.created_at))
            .offset(offset)
            .limit(limit)
        )
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, Task) else item[0] for item in results]

    def _workbench_filters(
        self,
        *,
        tab: str | None = None,
        keyword: str | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        long_running_before: datetime | None = None,
    ) -> list:
        filters = [
            Task.tenant_id == self.ctx.tenant_id,
            Task.workspace_id == self.ctx.workspace_id,
        ]
        normalized_tab = (tab or "all").strip().lower()
        active_statuses = ("queued", "preparing", "running", "retrying")

        if normalized_tab == "waiting_approval":
            filters.append(Task.status == "waiting_approval")
        elif normalized_tab == "failed":
            filters.append(Task.status == "failed")
        elif normalized_tab == "waiting_input":
            filters.append(Task.status == "waiting_input")
        elif normalized_tab == "running":
            filters.append(Task.status == "running")
        elif normalized_tab == "long_running" and long_running_before is not None:
            filters.append(Task.status.in_(active_statuses))
            filters.append(func.coalesce(Task.started_at, Task.created_at) <= long_running_before)

        if status:
            filters.append(Task.status == status)
        if date_from is not None:
            filters.append(Task.updated_at >= date_from)
        if date_to is not None:
            filters.append(Task.updated_at <= date_to)

        normalized_keyword = (keyword or "").strip()
        if normalized_keyword:
            pattern = f"%{normalized_keyword}%"
            filters.append(
                or_(
                    Task.id.ilike(pattern),
                    Task.task_type.ilike(pattern),
                    Task.status.ilike(pattern),
                    Task.agent_id.ilike(pattern),
                    Task.thread_id.ilike(pattern),
                    Task.run_id.ilike(pattern),
                    Task.error_code.ilike(pattern),
                    Task.error_message.ilike(pattern),
                    Task.created_by.ilike(pattern),
                    Task.updated_by.ilike(pattern),
                )
            )
        return filters

    def count_workbench_tasks(
        self,
        *,
        tab: str | None = None,
        keyword: str | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        long_running_before: datetime | None = None,
    ) -> int:
        query = select(func.count()).select_from(Task).where(
            and_(
                *self._workbench_filters(
                    tab=tab,
                    keyword=keyword,
                    status=status,
                    date_from=date_from,
                    date_to=date_to,
                    long_running_before=long_running_before,
                )
            )
        )
        result = self.db.exec(query).first()
        return self._count_value(result)

    def count_created_between(self, start_at: datetime, end_at: datetime) -> int:
        query = select(func.count()).select_from(Task).where(
            and_(
                Task.tenant_id == self.ctx.tenant_id,
                Task.workspace_id == self.ctx.workspace_id,
                Task.created_at >= start_at,
                Task.created_at <= end_at,
            )
        )
        result = self.db.exec(query).first()
        return self._count_value(result)

    def count_completed_between(self, start_at: datetime, end_at: datetime) -> int:
        query = select(func.count()).select_from(Task).where(
            and_(
                Task.tenant_id == self.ctx.tenant_id,
                Task.workspace_id == self.ctx.workspace_id,
                Task.status == "succeeded",
                Task.finished_at >= start_at,
                Task.finished_at <= end_at,
            )
        )
        result = self.db.exec(query).first()
        return self._count_value(result)

    def list_workbench_tasks(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        tab: str | None = None,
        keyword: str | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        long_running_before: datetime | None = None,
    ) -> list[Task]:
        query = (
            select(Task)
            .where(
                and_(
                    *self._workbench_filters(
                        tab=tab,
                        keyword=keyword,
                        status=status,
                        date_from=date_from,
                        date_to=date_to,
                        long_running_before=long_running_before,
                    )
                )
            )
            .order_by(desc(Task.updated_at), desc(Task.created_at))
            .offset(offset)
            .limit(limit)
        )
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, Task) else item[0] for item in results]

    def update_task(
        self,
        task: Task,
        *,
        outbox_events: Sequence[str] | None = None,
    ) -> Task:
        task.updated_at = utc_now()
        task.updated_by = self.ctx.user_id
        self.db.add(task)
        self.db.flush()
        for et in outbox_events or []:
            enqueue_task_outbox_event(self.db, self.ctx, event_type=et, task=task)
        self.db.flush()
        self.db.refresh(task)
        return task

    def add_checkpoint(self, checkpoint: TaskCheckpoint) -> TaskCheckpoint:
        checkpoint.tenant_id = self.ctx.tenant_id
        checkpoint.workspace_id = self.ctx.workspace_id
        self.db.add(checkpoint)
        self.db.flush()
        task = self.get_task(checkpoint.task_id)
        if task:
            enqueue_task_checkpoint_outbox(self.db, self.ctx, task=task, checkpoint=checkpoint)
        self.db.flush()
        self.db.refresh(checkpoint)
        return checkpoint

    def list_checkpoints(self, task_id: str) -> list[TaskCheckpoint]:
        query = (
            select(TaskCheckpoint)
            .where(
                and_(
                    TaskCheckpoint.task_id == task_id,
                    TaskCheckpoint.tenant_id == self.ctx.tenant_id,
                    TaskCheckpoint.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(TaskCheckpoint.checkpoint_no.asc())
        )
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, TaskCheckpoint) else item[0] for item in results]

    def add_event(self, event: TaskEvent) -> TaskEvent:
        event.tenant_id = self.ctx.tenant_id
        event.workspace_id = self.ctx.workspace_id
        self.db.add(event)
        self.db.flush()
        self.db.refresh(event)
        return event

    def list_events(self, task_id: str) -> list[TaskEvent]:
        query = (
            select(TaskEvent)
            .where(
                and_(
                    TaskEvent.task_id == task_id,
                    TaskEvent.tenant_id == self.ctx.tenant_id,
                    TaskEvent.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(TaskEvent.created_at.asc())
        )
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, TaskEvent) else item[0] for item in results]
