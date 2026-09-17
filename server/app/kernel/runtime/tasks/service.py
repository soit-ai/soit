"""Task lifecycle service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import ConflictError, NotFoundError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.observe.execution_metrics import observe_task_lifecycle
from app.kernel.runtime.db.models.tasks import Task, TaskCheckpoint, TaskEvent
from app.kernel.runtime.status import TaskStatus, validate_task_transition
from app.kernel.runtime.tasks.drivers import is_drivable
from app.kernel.runtime.tasks.events import TaskEventType
from app.kernel.runtime.tasks.protocols import TaskRepositoryProtocol
from app.kernel.runtime.tasks.repository import TaskRepository


class TaskService:
    """Coordinates task lifecycle persistence."""

    def __init__(
        self,
        db: AsyncSession | None,
        ctx: RequestContext,
        *,
        task_repo: TaskRepositoryProtocol | None = None,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.task_repo = task_repo or TaskRepository(db, ctx)

    async def create_task(
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

        task = await self.task_repo.create_task(
            Task(
                task_type=task_type,
                status=status,
                agent_id=agent_id,
                thread_id=thread_id,
                run_id=run_id,
                input_json=input_payload or {},
            )
        )
        await self.add_task_event(
            task_id=task.id,
            event_type="task.created",
            payload={"status": task.status, "task_type": task.task_type},
        )
        observe_task_lifecycle(task, TaskEventType.CREATED)
        return task

    async def get_task(self, task_id: str) -> Task:
        """Load a task or fail."""

        task = await self.task_repo.get_task(task_id)
        if not task:
            raise NotFoundError(f"Task not found: {task_id}")
        return task

    async def transition_task(
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

        task = await self.task_repo.get_task(task_id)
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

        # Lifecycle facts are durable in task_events and observed here; only a
        # retry goes through the outbox, because re-driving it must happen
        # exactly once.
        observed: list[str] = []
        _ready = (TaskStatus.PREPARING.value, TaskStatus.RUNNING.value)
        _from_queue = (
            TaskStatus.QUEUED.value,
            TaskStatus.RETRYING.value,
            TaskStatus.PAUSED.value,
            TaskStatus.WAITING_INPUT.value,
            TaskStatus.WAITING_APPROVAL.value,
        )
        if task.status in _ready and old_status in _from_queue:
            observed.append(TaskEventType.STARTED)
        if task.status == TaskStatus.SUCCEEDED.value:
            observed.append(TaskEventType.COMPLETED)
        if task.status == TaskStatus.FAILED.value:
            observed.append(TaskEventType.FAILED)

        task = await self.task_repo.update_task(task)
        for fact in observed:
            observe_task_lifecycle(task, fact)
        await self.add_task_event(
            task_id=task.id,
            event_type="task.status",
            payload={
                "status": task.status,
                "progress": task.progress_json,
                "error_code": task.error_code,
            },
        )
        return task

    def _require_driver(self, task: Task) -> None:
        """Reject a retry of a task type that nothing can run.

        Without this the status would flip to queued and the task would wait
        forever, which reads as accepted work that never completes. Resuming is
        not gated: approval and agent flows drive that path themselves.
        """

        if not is_drivable(task.task_type):
            raise ConflictError(
                f"Re-execution of task type {task.task_type!r} is not implemented"
            )

    async def cancel_task(self, *, task_id: str) -> Task:
        """Cancel an in-flight or waiting task."""

        task = await self.get_task(task_id)
        if task.status in {
            TaskStatus.SUCCEEDED.value,
            TaskStatus.FAILED.value,
            TaskStatus.CANCELED.value,
            TaskStatus.EXPIRED.value,
        }:
            return task
        return await self.transition_task(
            task_id=task_id,
            status=TaskStatus.CANCELED.value,
            progress={"action": "cancel"},
        )

    async def resume_task(self, *, task_id: str) -> Task:
        """Resume a paused or waiting task."""

        task = await self.get_task(task_id)
        if task.status not in {
            TaskStatus.PAUSED.value,
            TaskStatus.WAITING_INPUT.value,
            TaskStatus.WAITING_APPROVAL.value,
        }:
            return task
        return await self.transition_task(
            task_id=task_id,
            status=TaskStatus.RUNNING.value,
            progress={**(task.progress_json or {}), "action": "resume"},
        )

    async def retry_task(self, *, task_id: str) -> Task:
        """Retry a failed task by re-queuing it."""

        task = await self.get_task(task_id)
        if task.status not in {
            TaskStatus.FAILED.value,
            TaskStatus.CANCELED.value,
            TaskStatus.EXPIRED.value,
        }:
            return task
        self._require_driver(task)
        task.started_at = None
        task.finished_at = None
        task.error_code = None
        task.error_message = None
        task.output_json = {}
        task.progress_json = {"action": "retry"}
        task.status = TaskStatus.RETRYING.value
        task = await self.task_repo.update_task(task, outbox_events=[TaskEventType.RETRIED])
        await self.add_task_event(
            task_id=task.id,
            event_type="task.retry",
            payload={"status": task.status},
        )
        return await self.transition_task(
            task_id=task.id,
            status=TaskStatus.QUEUED.value,
            progress={"action": "requeued"},
        )

    async def add_checkpoint(
        self,
        *,
        task_id: str,
        checkpoint_no: int,
        status: str,
        payload: dict[str, Any] | None = None,
    ) -> TaskCheckpoint:
        """Store a task checkpoint and append a matching event."""

        checkpoint = await self.task_repo.add_checkpoint(
            TaskCheckpoint(
                task_id=task_id,
                checkpoint_no=checkpoint_no,
                status=status,
                payload_json=payload or {},
            )
        )
        await self.add_task_event(
            task_id=task_id,
            event_type="task.checkpoint",
            payload={"checkpoint_no": checkpoint_no, "status": status},
        )
        task = await self.task_repo.get_task(task_id)
        if task is not None:
            observe_task_lifecycle(
                task,
                TaskEventType.CHECKPOINTED,
                checkpoint_no=checkpoint_no,
                checkpoint_status=status,
            )
        return checkpoint

    async def add_task_event(
        self,
        *,
        task_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> TaskEvent:
        """Append a task event."""

        return await self.task_repo.add_event(
            TaskEvent(
                task_id=task_id,
                event_type=event_type,
                payload_json=payload or {},
            )
        )
