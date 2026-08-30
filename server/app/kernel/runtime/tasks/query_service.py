"""Read-side services for runtime tasks."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.pagination import PageToken
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.tasks.drivers import is_drivable
from app.kernel.runtime.tasks.repository import TaskRepository
from app.kernel.runtime.tasks.schemas import (
    TaskCheckpointResponse,
    TaskEventResponse,
    TaskHandlingResponse,
    TaskHandlingSummary,
    TaskResponse,
    TaskRuntimeContext,
    TaskWorkbenchItemsResponse,
    TaskWorkbenchResponse,
    TaskWorkbenchRow,
    TaskWorkbenchSummary,
    TaskWorkbenchTabs,
)


class TaskQueryService:
    """Read-only access to runtime task records."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx
        self.task_repo = TaskRepository(db, ctx)

    def list_tasks(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
        task_type: str | None = None,
        agent_id: str | None = None,
        thread_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[Task]:
        return self.task_repo.list_tasks(
            limit=limit,
            offset=offset,
            status=status,
            task_type=task_type,
            agent_id=agent_id,
            thread_id=thread_id,
            since=since,
            until=until,
        )

    def count_tasks(
        self,
        *,
        status: str | None = None,
        task_type: str | None = None,
        agent_id: str | None = None,
        thread_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> int:
        """Count tasks matching the same filters ``list_tasks`` accepts."""
        return self.task_repo.count_tasks(
            status=status,
            task_type=task_type,
            agent_id=agent_id,
            thread_id=thread_id,
            since=since,
            until=until,
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

    def get_task_workbench(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> TaskWorkbenchResponse:
        threshold = self._long_running_before()
        summary = self._build_workbench_summary(threshold)
        tabs = TaskWorkbenchTabs(
            all=summary.total_tasks,
            waiting_approval=summary.waiting_approval,
            failed=summary.failed,
            waiting_input=summary.waiting_input,
            long_running=summary.long_running,
            running=summary.running,
        )
        items_response = self.get_task_workbench_items(
            limit=limit,
            offset=offset,
            tab="all",
            keyword=None,
            status=None,
            date_from=None,
            date_to=None,
        )
        return TaskWorkbenchResponse(
            summary=summary,
            tabs=tabs,
            items=items_response.items,
            total=items_response.total,
            next_page_token=items_response.next_page_token,
            page_size=items_response.page_size,
        )

    def get_task_workbench_items(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        tab: str | None = None,
        keyword: str | None = None,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> TaskWorkbenchItemsResponse:
        threshold = self._long_running_before()
        start_at = self._parse_date_start(date_from)
        end_at = self._parse_date_end(date_to)
        total = self.task_repo.count_workbench_tasks(
            tab=tab,
            keyword=keyword,
            status=status,
            date_from=start_at,
            date_to=end_at,
            long_running_before=threshold,
        )
        tasks = self.task_repo.list_workbench_tasks(
            limit=limit,
            offset=offset,
            tab=tab,
            keyword=keyword,
            status=status,
            date_from=start_at,
            date_to=end_at,
            long_running_before=threshold,
        )
        next_offset = offset + len(tasks)
        next_page_token = PageToken(offset=next_offset, limit=limit).to_string() if next_offset < total else None
        return TaskWorkbenchItemsResponse(
            items=[self._task_to_workbench_row(task) for task in tasks],
            total=total,
            next_page_token=next_page_token,
            page_size=len(tasks),
        )

    def get_task_handling(self, task_id: str) -> TaskHandlingResponse:
        task = self.get_task(task_id)
        events = self.task_repo.list_events(task_id)
        checkpoints = self.task_repo.list_checkpoints(task_id)
        title = self._display_name(task)
        return TaskHandlingResponse(
            task=TaskResponse.model_validate(task),
            summary=TaskHandlingSummary(
                title=title,
                status=task.status,
                task_type=task.task_type,
                error_code=task.error_code,
                error_message=task.error_message,
                updated_at=task.updated_at,
            ),
            runtime_context=TaskRuntimeContext(
                agent_id=task.agent_id,
                thread_id=task.thread_id,
                run_id=task.run_id,
            ),
            available_actions=self._available_actions(task),
            events=[TaskEventResponse.model_validate(item) for item in events],
            checkpoints=[TaskCheckpointResponse.model_validate(item) for item in checkpoints],
        )

    def _build_workbench_summary(self, long_running_before: datetime) -> TaskWorkbenchSummary:
        now = utc_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1) - timedelta(microseconds=1)
        return TaskWorkbenchSummary(
            total_tasks=self.task_repo.count_workbench_tasks(long_running_before=long_running_before),
            waiting_approval=self.task_repo.count_workbench_tasks(tab="waiting_approval", long_running_before=long_running_before),
            failed=self.task_repo.count_workbench_tasks(tab="failed", long_running_before=long_running_before),
            waiting_input=self.task_repo.count_workbench_tasks(tab="waiting_input", long_running_before=long_running_before),
            long_running=self.task_repo.count_workbench_tasks(tab="long_running", long_running_before=long_running_before),
            running=self.task_repo.count_workbench_tasks(tab="running", long_running_before=long_running_before),
            today_created=self.task_repo.count_created_between(today_start, today_end),
            today_completed=self.task_repo.count_completed_between(today_start, today_end),
            updated_at=now,
        )

    def _task_to_workbench_row(self, task: Task) -> TaskWorkbenchRow:
        return TaskWorkbenchRow(
            id=task.id,
            tenant_id=task.tenant_id,
            workspace_id=task.workspace_id,
            display_name=self._display_name(task),
            task_type=task.task_type,
            status=task.status,
            agent_id=task.agent_id,
            thread_id=task.thread_id,
            run_id=task.run_id,
            owner=task.updated_by or task.created_by,
            error_code=task.error_code,
            error_message=task.error_message,
            created_at=task.created_at,
            updated_at=task.updated_at,
            started_at=task.started_at,
            finished_at=task.finished_at,
        )

    def _display_name(self, task: Task) -> str:
        for key in ("title", "demo_title", "name"):
            value = (task.input_json or {}).get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return task.task_type

    def available_actions(self, task: Task) -> list[str]:
        """Return the controls a caller may invoke for this task."""
        return self._available_actions(task)

    def _available_actions(self, task: Task) -> list[str]:
        # Only advertise retry when something is registered to re-run the task
        # from scratch. Offering it otherwise leaves the task queued forever.
        # Resume is always available: approval and agent flows drive it.
        if task.status in {"failed", "canceled", "expired"}:
            return ["retry"] if is_drivable(task.task_type) else []
        if task.status in {"paused", "waiting_input", "waiting_approval"}:
            return ["resume", "cancel"]
        if task.status in {"queued", "preparing", "running", "retrying"}:
            return ["cancel"]
        return []

    def _long_running_before(self) -> datetime:
        return utc_now() - timedelta(minutes=30)

    def _parse_date_start(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed
        return datetime.combine(parsed.date(), time.min, tzinfo=UTC)

    def _parse_date_end(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed
        return datetime.combine(parsed.date(), time.max, tzinfo=UTC)
