"""Thread persistence models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Index, Text, UniqueConstraint
from sqlmodel import JSON, Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


def generate_thread_id() -> str:
    """Generate a Thread identifier."""

    return f"thr_{generate_ulid()}"


def generate_thread_message_id() -> str:
    """Generate a ThreadMessage identifier."""

    return f"thmsg_{generate_ulid()}"



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
    agent_id: str | None = Field(default=None, index=True)
    title: str | None = Field(default=None, nullable=True)
    status: str = Field(default="active", index=True)
    thread_type: str = Field(default="chat", index=True)
    source: str | None = Field(default=None, nullable=True, index=True)
    owner_user_id: str | None = Field(default=None, nullable=True, index=True)
    summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    system_prompt: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    default_model_ref: str | None = Field(default=None, nullable=True)
    default_temperature: float | None = Field(default=None, nullable=True)
    default_max_tokens: int | None = Field(default=None, nullable=True)
    default_top_p: float | None = Field(default=None, nullable=True)
    context_window: int | None = Field(default=None, nullable=True)
    max_history_messages: int | None = Field(default=None, nullable=True)
    max_history_chars: int | None = Field(default=None, nullable=True)
    message_count: int = Field(default=0)
    last_message_at: datetime | None = Field(default=None, nullable=True, index=True)
    last_user_message_at: datetime | None = Field(default=None, nullable=True)
    last_assistant_message_at: datetime | None = Field(default=None, nullable=True)
    archived_at: datetime | None = Field(default=None, nullable=True)
    pinned_at: datetime | None = Field(default=None, nullable=True)
    knowledge_config_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    tool_config_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    latest_run_id: str | None = Field(default=None, nullable=True, index=True)
    created_by: str | None = Field(default=None, nullable=True)
    updated_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    deleted_at: datetime | None = Field(default=None, nullable=True)
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
    thread_id: str = Field(index=True)
    run_id: str | None = Field(default=None, index=True)
    task_id: str | None = Field(default=None, index=True)
    response_id: str | None = Field(default=None, index=True)
    parent_message_id: str | None = Field(default=None, index=True)
    sequence_no: int = Field(default=0, index=True)
    role: str = Field()
    content: str = Field()
    message_type: str = Field(default="text")
    status: str = Field(default="completed", index=True)
    content_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    model_ref: str | None = Field(default=None, nullable=True)
    tokens_prompt: int | None = Field(default=None, nullable=True)
    tokens_completion: int | None = Field(default=None, nullable=True)
    finish_reason: str | None = Field(default=None, nullable=True)
    citations_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    attachments_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    tool_calls_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    error_code: str | None = Field(default=None, nullable=True)
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    edited_at: datetime | None = Field(default=None, nullable=True)
    deleted_at: datetime | None = Field(default=None, nullable=True)
