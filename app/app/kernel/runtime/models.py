"""Runtime core persistence models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, Text, UniqueConstraint
from sqlmodel import JSON, Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now
from app.kernel.runtime.contracts.status import TaskStatus


def generate_thread_id() -> str:
    """Generate a Thread identifier."""

    return f"thr_{generate_ulid()}"


def generate_thread_message_id() -> str:
    """Generate a ThreadMessage identifier."""

    return f"thmsg_{generate_ulid()}"


def generate_task_id() -> str:
    """Generate a Task identifier."""

    return f"task_{generate_ulid()}"


def generate_task_checkpoint_id() -> str:
    """Generate a TaskCheckpoint identifier."""

    return f"tcp_{generate_ulid()}"


def generate_task_event_id() -> str:
    """Generate a TaskEvent identifier."""

    return f"tevt_{generate_ulid()}"


class Thread(SQLModel, table=True):
    """Agent-scoped conversation container."""

    __tablename__ = "threads"
    __table_args__ = (
        Index("ix_threads_agent_status", "agent_id", "status"),
        Index("ix_threads_scope_updated", "tenant_id", "workspace_id", "updated_at"),
        Index("ix_threads_status_archived", "status", "archived_at"),
        Index("ix_threads_owner_updated", "owner_user_id", "updated_at"),
    )

    id: str = Field(primary_key=True, default_factory=generate_thread_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    agent_id: Optional[str] = Field(default=None, foreign_key="agents.id", index=True)
    title: Optional[str] = Field(default=None, nullable=True)
    status: str = Field(default="active", index=True)
    thread_type: str = Field(default="chat", index=True)
    source: Optional[str] = Field(default=None, nullable=True, index=True)
    owner_user_id: Optional[str] = Field(default=None, nullable=True, index=True)
    summary: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    system_prompt: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    default_model_ref: Optional[str] = Field(default=None, nullable=True)
    default_temperature: Optional[float] = Field(default=None, nullable=True)
    default_max_tokens: Optional[int] = Field(default=None, nullable=True)
    default_top_p: Optional[float] = Field(default=None, nullable=True)
    context_window: Optional[int] = Field(default=None, nullable=True)
    max_history_messages: Optional[int] = Field(default=None, nullable=True)
    max_history_chars: Optional[int] = Field(default=None, nullable=True)
    message_count: int = Field(default=0)
    last_message_at: Optional[datetime] = Field(default=None, nullable=True, index=True)
    last_user_message_at: Optional[datetime] = Field(default=None, nullable=True)
    last_assistant_message_at: Optional[datetime] = Field(default=None, nullable=True)
    archived_at: Optional[datetime] = Field(default=None, nullable=True)
    pinned_at: Optional[datetime] = Field(default=None, nullable=True)
    knowledge_config_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    tool_config_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    latest_run_id: Optional[str] = Field(default=None, nullable=True, index=True)
    created_by: Optional[str] = Field(default=None, nullable=True)
    updated_by: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)


class ThreadMessage(SQLModel, table=True):
    """Message ledger attached to a Thread."""

    __tablename__ = "thread_messages"
    __table_args__ = (
        UniqueConstraint("thread_id", "sequence_no", name="uq_thread_messages_thread_sequence"),
        Index("ix_thread_messages_thread_created", "thread_id", "created_at"),
        Index("ix_thread_messages_thread_sequence", "thread_id", "sequence_no"),
        Index("ix_thread_messages_status_created", "status", "created_at"),
    )

    id: str = Field(primary_key=True, default_factory=generate_thread_message_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    thread_id: str = Field(foreign_key="threads.id", index=True)
    run_id: Optional[str] = Field(default=None, foreign_key="runs.id", index=True)
    task_id: Optional[str] = Field(default=None, foreign_key="tasks.id", index=True)
    response_id: Optional[str] = Field(default=None, foreign_key="responses.id", index=True)
    parent_message_id: Optional[str] = Field(default=None, foreign_key="thread_messages.id", index=True)
    sequence_no: int = Field(default=0, index=True)
    role: str = Field()
    content: str = Field()
    message_type: str = Field(default="text")
    status: str = Field(default="completed", index=True)
    content_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    summary: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    model_ref: Optional[str] = Field(default=None, nullable=True)
    tokens_prompt: Optional[int] = Field(default=None, nullable=True)
    tokens_completion: Optional[int] = Field(default=None, nullable=True)
    finish_reason: Optional[str] = Field(default=None, nullable=True)
    citations_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    attachments_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    tool_calls_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    error_code: Optional[str] = Field(default=None, nullable=True)
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_by: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    edited_at: Optional[datetime] = Field(default=None, nullable=True)
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)


class Task(SQLModel, table=True):
    """Platform-level long-running task."""

    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_agent_status", "agent_id", "status"),
        Index("ix_tasks_run_status", "run_id", "status"),
    )

    id: str = Field(primary_key=True, default_factory=generate_task_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    agent_id: Optional[str] = Field(default=None, foreign_key="agents.id", index=True)
    thread_id: Optional[str] = Field(default=None, foreign_key="threads.id", index=True)
    run_id: Optional[str] = Field(default=None, foreign_key="runs.id", index=True)
    task_type: str = Field(index=True)
    status: str = Field(default=TaskStatus.QUEUED.value, index=True)
    input_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    output_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    progress_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    error_code: Optional[str] = Field(default=None, nullable=True)
    error_message: Optional[str] = Field(default=None, nullable=True)
    started_at: Optional[datetime] = Field(default=None, nullable=True)
    finished_at: Optional[datetime] = Field(default=None, nullable=True)
    created_by: Optional[str] = Field(default=None, nullable=True)
    updated_by: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class TaskCheckpoint(SQLModel, table=True):
    """Checkpoint snapshots for resumable tasks."""

    __tablename__ = "task_checkpoints"
    __table_args__ = (
        UniqueConstraint("task_id", "checkpoint_no", name="uq_task_checkpoint_no"),
        Index("ix_task_checkpoints_task_id", "task_id"),
    )

    id: str = Field(primary_key=True, default_factory=generate_task_checkpoint_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    task_id: str = Field(foreign_key="tasks.id")
    checkpoint_no: int = Field()
    status: str = Field(default=TaskStatus.QUEUED.value)
    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)


class TaskEvent(SQLModel, table=True):
    """Event ledger for task lifecycle updates."""

    __tablename__ = "task_events"
    __table_args__ = (
        Index("ix_task_events_task_created", "task_id", "created_at"),
    )

    id: str = Field(primary_key=True, default_factory=generate_task_event_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    task_id: str = Field(foreign_key="tasks.id", index=True)
    event_type: str = Field(index=True)
    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
