"""Task persistence models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import JSON, Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now
from app.kernel.runtime.status import TaskStatus


def generate_task_id() -> str:
    """Generate a Task identifier."""

    return f"task_{generate_ulid()}"


def generate_task_checkpoint_id() -> str:
    """Generate a TaskCheckpoint identifier."""

    return f"tcp_{generate_ulid()}"


def generate_task_event_id() -> str:
    """Generate a TaskEvent identifier."""

    return f"tevt_{generate_ulid()}"



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
    agent_id: str | None = Field(default=None, index=True)
    thread_id: str | None = Field(default=None, index=True)
    run_id: str | None = Field(default=None, index=True)
    task_type: str = Field(index=True)
    status: str = Field(default=TaskStatus.QUEUED.value, index=True)
    input_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    output_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    progress_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    error_code: str | None = Field(default=None, nullable=True)
    error_message: str | None = Field(default=None, nullable=True)
    started_at: datetime | None = Field(default=None, nullable=True)
    finished_at: datetime | None = Field(default=None, nullable=True)
    created_by: str | None = Field(default=None, nullable=True)
    updated_by: str | None = Field(default=None, nullable=True)
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
    task_id: str = Field()
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
    task_id: str = Field(index=True)
    event_type: str = Field(index=True)
    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
