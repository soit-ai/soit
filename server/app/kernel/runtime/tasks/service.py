"""Task lifecycle service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.tasks import Task, TaskCheckpoint, TaskEvent
from app.kernel.runtime.tasks.events import TaskEventType
from app.kernel.runtime.tasks.protocols import TaskRepositoryProtocol
from app.kernel.runtime.tasks.repository import TaskRepository
from app.kernel.runtime.tasks.status import TaskStatus, validate_task_transition


class TaskService:
    """Coordinates task lifecycle persistence."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        *,
        task_repo: TaskRepositoryProtocol | None = None,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.task_repo = task_repo or TaskRepository(db, ctx)

    def create_task(
        self,
        *,
        task_type: str,
        status: str = TaskStatus.QUEUED.value,
        agent_id: str | None = None,
        thread_id: str | None = None,
        run_id: str | None = None,
        input_payload: dict[str, Any] | None = None,
    ) -> Task:
        """Create a task record."""

        task = self.task_repo.create_task(
            Task(
                task_type=task_type,
                status=status,
                agent_id=agent_id,
                thread_id=thread_id,
                run_id=run_id,
                input_json=input_payload or {},
            )
        )
        self.add_task_event(
            task_id=task.id,
            event_type="task.created",
            payload={"status": task.status, "task_type": task.task_type},
        )
        return task

    def get_task(self, task_id: str) -> Task:
        """Load a task or fail."""

        task = self.task_repo.get_task(task_id)
        if not task:
            raise NotFoundError(f"Task not found: {task_id}")
        return task

    def transition_task(
        self,
        *,
        task_id: str,
        status: str,
        progress: dict[str, Any] | None = None,
        output_payload: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        timestamp: datetime | None = None,
    ) -> Task:
        """Transition task status and record a task event."""

        task = self.task_repo.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        old_status = task.status
        status = validate_task_transition(old_status, status)
        now = timestamp or utc_now()
        if status in {TaskStatus.RUNNING.value, TaskStatus.PREPARING.value} and task.started_at is None:
            task.started_at = now
        if status in {
            TaskStatus.SUCCEEDED.value,
            TaskStatus.FAILED.value,
            TaskStatus.CANCELED.value,
            TaskStatus.EXPIRED.value,
        }:
            task.finished_at = now

        task.status = status
        if progress is not None:
            task.progress_json = progress
        if output_payload is not None:
            task.output_json = output_payload
        if error_code is not None:
            task.error_code = error_code
        if error_message is not None:
            task.error_message = error_message

        outbox_events: list[str] = []
        _ready = (TaskStatus.PREPARING.value, TaskStatus.RUNNING.value)
        _from_queue = (
            TaskStatus.QUEUED.value,
            TaskStatus.RETRYING.value,
            TaskStatus.PAUSED.value,
            TaskStatus.WAITING_INPUT.value,
            TaskStatus.WAITING_APPROVAL.value,
        )
        if task.status in _ready and old_status in _from_queue:
            outbox_events.append(TaskEventType.STARTED)
        if task.status == TaskStatus.SUCCEEDED.value:
            outbox_events.append(TaskEventType.COMPLETED)
        if task.status == TaskStatus.FAILED.value:
            outbox_events.append(TaskEventType.FAILED)

        task = self.task_repo.update_task(task, outbox_events=outbox_events)
        self.add_task_event(
            task_id=task.id,
            event_type="task.status",
            payload={
                "status": task.status,
                "progress": task.progress_json,
                "error_code": task.error_code,
            },
        )
        return task

    def cancel_task(self, *, task_id: str) -> Task:
        """Cancel an in-flight or waiting task."""

        task = self.get_task(task_id)
        if task.status in {
            TaskStatus.SUCCEEDED.value,
            TaskStatus.FAILED.value,
            TaskStatus.CANCELED.value,
            TaskStatus.EXPIRED.value,
        }:
            return task
        return self.transition_task(
            task_id=task_id,
            status=TaskStatus.CANCELED.value,
            progress={"action": "cancel"},
        )

    def resume_task(self, *, task_id: str) -> Task:
        """Resume a paused or waiting task."""

        task = self.get_task(task_id)
        if task.status not in {
            TaskStatus.PAUSED.value,
            TaskStatus.WAITING_INPUT.value,
            TaskStatus.WAITING_APPROVAL.value,
        }:
            return task
        return self.transition_task(
            task_id=task_id,
            status=TaskStatus.RUNNING.value,
            progress={"action": "resume"},
        )

    def retry_task(self, *, task_id: str) -> Task:
        """Retry a failed task by re-queuing it."""

        task = self.get_task(task_id)
        if task.status not in {
            TaskStatus.FAILED.value,
            TaskStatus.CANCELED.value,
            TaskStatus.EXPIRED.value,
        }:
            return task
        task.started_at = None
        task.finished_at = None
        task.error_code = None
        task.error_message = None
        task.output_json = {}
        task.progress_json = {"action": "retry"}
        task.status = TaskStatus.RETRYING.value
        task = self.task_repo.update_task(task, outbox_events=[TaskEventType.RETRIED])
        self.add_task_event(
            task_id=task.id,
            event_type="task.retry",
            payload={"status": task.status},
        )
        return self.transition_task(
            task_id=task.id,
            status=TaskStatus.QUEUED.value,
            progress={"action": "requeued"},
        )

    def add_checkpoint(
        self,
        *,
        task_id: str,
        checkpoint_no: int,
        status: str,
        payload: dict[str, Any] | None = None,
    ) -> TaskCheckpoint:
        """Store a task checkpoint and append a matching event."""

        checkpoint = self.task_repo.add_checkpoint(
            TaskCheckpoint(
                task_id=task_id,
                checkpoint_no=checkpoint_no,
                status=status,
                payload_json=payload or {},
            )
        )
        self.add_task_event(
            task_id=task_id,
            event_type="task.checkpoint",
            payload={"checkpoint_no": checkpoint_no, "status": status},
        )
        return checkpoint

    def add_task_event(
        self,
        *,
        task_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> TaskEvent:
        """Append a task event."""

        return self.task_repo.add_event(
            TaskEvent(
                task_id=task_id,
                event_type=event_type,
                payload_json=payload or {},
            )
        )
