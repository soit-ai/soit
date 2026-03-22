"""Persistence models for the Responses API resource layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import JSON, Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


def generate_response_id() -> str:
    """Generate a Response identifier."""

    return f"resp_{generate_ulid()}"


def generate_response_event_id() -> str:
    """Generate a ResponseEvent identifier."""

    return f"revt_{generate_ulid()}"


class Response(SQLModel, table=True):
    """Northbound response resource projected from run-scoped execution."""

    __tablename__ = "responses"
    __table_args__ = (
        Index("ix_responses_scope_status_created", "tenant_id", "workspace_id", "status", "created_at"),
        Index("ix_responses_thread_created", "thread_id", "created_at"),
        Index("ix_responses_agent_created", "agent_id", "created_at"),
    )

    id: str = Field(primary_key=True, default_factory=generate_response_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    thread_id: Optional[str] = Field(default=None, foreign_key="threads.id", index=True)
    task_id: Optional[str] = Field(default=None, foreign_key="tasks.id", index=True)
    agent_id: Optional[str] = Field(default=None, foreign_key="agents.id", index=True)
    run_id: Optional[str] = Field(default=None, foreign_key="runs.id", index=True)
    model: Optional[str] = Field(default=None, index=True)
    provider: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="queued", index=True)
    input_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    output_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    usage_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    error_code: Optional[str] = Field(default=None, nullable=True)
    error_message: Optional[str] = Field(default=None, nullable=True)
    created_by: Optional[str] = Field(default=None, nullable=True)
    updated_by: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = Field(default=None, nullable=True)
    canceled_at: Optional[datetime] = Field(default=None, nullable=True)


class ResponseEvent(SQLModel, table=True):
    """Persisted semantic event stream projected for response consumers."""

    __tablename__ = "response_events"
    __table_args__ = (
        UniqueConstraint("response_id", "sequence", name="uq_response_events_response_sequence"),
        Index("ix_response_events_response_created", "response_id", "created_at"),
        Index("ix_response_events_run_created", "run_id", "created_at"),
        Index("ix_response_events_type_created", "type", "created_at"),
    )

    id: str = Field(primary_key=True, default_factory=generate_response_event_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    response_id: str = Field(foreign_key="responses.id", index=True)
    run_id: Optional[str] = Field(default=None, foreign_key="runs.id", index=True)
    thread_id: Optional[str] = Field(default=None, foreign_key="threads.id", index=True)
    task_id: Optional[str] = Field(default=None, foreign_key="tasks.id", index=True)
    agent_id: Optional[str] = Field(default=None, foreign_key="agents.id", index=True)
    sequence: int = Field(index=True)
    type: str = Field(index=True)
    source: str = Field(default="responses", index=True)
    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
