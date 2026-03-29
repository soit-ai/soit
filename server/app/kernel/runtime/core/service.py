"""Minimal Runtime Core service.

This service centralizes Thread and Task lifecycle operations without
duplicating thread/task persistence across chat, agent, and workflow adapters.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError
from app.kernel.contracts.context import RequestContext
from app.kernel.commons.time import utc_now
from app.kernel.runtime.contracts.status import TaskStatus
from app.kernel.runtime.events import TaskEventType
from app.kernel.runtime.models import Task, TaskCheckpoint, TaskEvent, Thread, ThreadMessage
from app.kernel.runtime.repository import TaskRepository, ThreadRepository


class RuntimeCoreService:
    """Coordinates Thread and Task persistence for the Runtime Core."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx
        self.thread_repo = ThreadRepository(db, ctx)
        self.task_repo = TaskRepository(db, ctx)

    def create_thread(
        self,
        *,
        agent_id: Optional[str],
        title: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        summary: Optional[str] = None,
        system_prompt: Optional[str] = None,
        default_model_ref: Optional[str] = None,
        default_temperature: Optional[float] = None,
        default_max_tokens: Optional[int] = None,
        default_top_p: Optional[float] = None,
        context_window: Optional[int] = None,
        max_history_messages: Optional[int] = None,
        max_history_chars: Optional[int] = None,
        knowledge_config_json: Optional[dict[str, Any]] = None,
        tool_config_json: Optional[dict[str, Any]] = None,
        thread_type: str = "chat",
        source: Optional[str] = None,
        owner_user_id: Optional[str] = None,
    ) -> Thread:
        """Create an Agent-scoped thread."""

        return self.thread_repo.create_thread(
            Thread(
                agent_id=agent_id,
                title=title,
                summary=summary,
                system_prompt=system_prompt,
                default_model_ref=default_model_ref,
                default_temperature=default_temperature,
                default_max_tokens=default_max_tokens,
                default_top_p=default_top_p,
                context_window=context_window,
                max_history_messages=max_history_messages,
                max_history_chars=max_history_chars,
                knowledge_config_json=knowledge_config_json or {},
                tool_config_json=tool_config_json or {},
                thread_type=thread_type,
                source=source or ((metadata or {}).get("source") if isinstance(metadata, dict) else None),
                owner_user_id=owner_user_id or self.ctx.user_id,
                metadata_json=metadata or {},
            )
        )

    def get_thread(self, thread_id: str) -> Thread:
        """Load a thread or fail."""

        thread = self.thread_repo.get_thread(thread_id)
        if not thread:
            raise NotFoundError(f"Thread not found: {thread_id}")
        return thread

    def update_thread(
        self,
        *,
        thread_id: str,
        title: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        latest_run_id: Optional[str] = None,
        summary: Optional[str] = None,
        system_prompt: Optional[str] = None,
        default_model_ref: Optional[str] = None,
        default_temperature: Optional[float] = None,
        default_max_tokens: Optional[int] = None,
        default_top_p: Optional[float] = None,
        context_window: Optional[int] = None,
        max_history_messages: Optional[int] = None,
        max_history_chars: Optional[int] = None,
        knowledge_config_json: Optional[dict[str, Any]] = None,
        tool_config_json: Optional[dict[str, Any]] = None,
        thread_type: Optional[str] = None,
        source: Optional[str] = None,
        pinned_at: Any = ...,
    ) -> Thread:
        """Update mutable thread fields."""

        thread = self.thread_repo.update_thread(
            thread_id,
            title=title,
            status=status,
            metadata=metadata,
            latest_run_id=latest_run_id,
            summary=summary,
            system_prompt=system_prompt,
            default_model_ref=default_model_ref,
            default_temperature=default_temperature,
            default_max_tokens=default_max_tokens,
            default_top_p=default_top_p,
            context_window=context_window,
            max_history_messages=max_history_messages,
            max_history_chars=max_history_chars,
            knowledge_config_json=knowledge_config_json,
            tool_config_json=tool_config_json,
            thread_type=thread_type,
            source=source,
            pinned_at=pinned_at,
        )
        if not thread:
            raise NotFoundError(f"Thread not found: {thread_id}")
        return thread

    def delete_thread(self, *, thread_id: str) -> None:
        """Soft-delete a thread."""

        thread = self.thread_repo.soft_delete_thread(thread_id)
        if not thread:
            raise NotFoundError(f"Thread not found: {thread_id}")

    def append_message(
        self,
        *,
        thread_id: str,
        role: str,
        content: str,
        run_id: Optional[str] = None,
        task_id: Optional[str] = None,
        response_id: Optional[str] = None,
        parent_message_id: Optional[str] = None,
        message_type: str = "text",
        metadata: Optional[dict[str, Any]] = None,
        status: str = "completed",
        model_ref: Optional[str] = None,
        tokens_prompt: Optional[int] = None,
        tokens_completion: Optional[int] = None,
        finish_reason: Optional[str] = None,
        content_json: Optional[dict[str, Any]] = None,
        summary: Optional[str] = None,
        citations_json: Optional[list[dict[str, Any]]] = None,
        attachments_json: Optional[list[dict[str, Any]]] = None,
        tool_calls_json: Optional[list[dict[str, Any]]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> ThreadMessage:
        """Append a message to a thread."""

        self.get_thread(thread_id)
        metadata_json = metadata or {}
        return self.thread_repo.add_message(
            ThreadMessage(
                thread_id=thread_id,
                run_id=run_id,
                task_id=task_id or metadata_json.get("task_id"),
                response_id=response_id or metadata_json.get("response_id"),
                parent_message_id=parent_message_id,
                role=role,
                content=content,
                message_type=message_type,
                status=status,
                model_ref=model_ref or metadata_json.get("model_ref") or metadata_json.get("model"),
                tokens_prompt=tokens_prompt if tokens_prompt is not None else metadata_json.get("tokens_prompt"),
                tokens_completion=(
                    tokens_completion if tokens_completion is not None else metadata_json.get("tokens_completion")
                ),
                finish_reason=finish_reason or metadata_json.get("finish_reason"),
                content_json=content_json or metadata_json.get("content_json") or {},
                summary=summary or metadata_json.get("summary"),
                citations_json=citations_json or metadata_json.get("citations") or [],
                attachments_json=attachments_json or metadata_json.get("attachments") or [],
                tool_calls_json=tool_calls_json or metadata_json.get("tool_calls") or [],
                error_code=error_code or metadata_json.get("error_code"),
                error_message=error_message or metadata_json.get("error_message"),
                metadata_json=metadata_json,
            )
        )

    def create_task(
        self,
        *,
        task_type: str,
        status: str = TaskStatus.QUEUED.value,
        agent_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        run_id: Optional[str] = None,
        input_payload: Optional[dict[str, Any]] = None,
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
        progress: Optional[dict[str, Any]] = None,
        output_payload: Optional[dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> Task:
        """Transition task status and record a task event."""

        task = self.task_repo.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        old_status = task.status
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
        _from_queue = (TaskStatus.QUEUED.value, TaskStatus.RETRYING.value)
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
        payload: Optional[dict[str, Any]] = None,
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
        payload: Optional[dict[str, Any]] = None,
    ) -> TaskEvent:
        """Append a task event."""

        return self.task_repo.add_event(
            TaskEvent(
                task_id=task_id,
                event_type=event_type,
                payload_json=payload or {},
            )
        )
