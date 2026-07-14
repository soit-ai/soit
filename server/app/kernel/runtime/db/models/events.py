"""Persistence models for transactional outbox (aligned with migration 20260323100000)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, Index, Text, UniqueConstraint
from sqlmodel import JSON, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


def generate_outbox_row_id() -> str:
    """Primary key for event_outbox rows."""

    return generate_ulid()


def generate_checkpoint_id() -> str:
    """Primary key for consumer checkpoint rows."""

    return generate_ulid()


class EventOutbox(SQLModel, table=True):
    """Outbox row: one domain event pending dispatch."""

    __tablename__ = "event_outbox"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_event_outbox_event_id"),
        Index("ix_event_outbox_status_available_at", "status", "available_at"),
        Index("ix_event_outbox_correlation_id", "correlation_id"),
        Index("ix_event_outbox_subject_type_subject_id", "subject_type", "subject_id"),
        Index("ix_event_outbox_run_id", "run_id"),
        Index("ix_event_outbox_workflow_run_id", "workflow_run_id"),
    )

    id: str = Field(primary_key=True, default_factory=generate_outbox_row_id)
    event_id: str = Field(index=True)
    event_type: str = Field(index=True)
    event_version: str = Field(default="1")
    tenant_id: str | None = Field(default=None, index=True)
    workspace_id: str | None = Field(default=None, index=True)
    idempotency_key: str = Field(index=True)
    subject_type: str | None = Field(default=None)
    subject_id: str | None = Field(default=None)
    run_id: str | None = Field(default=None)
    task_id: str | None = Field(default=None)
    thread_id: str | None = Field(default=None)
    workflow_run_id: str | None = Field(default=None)
    correlation_id: str | None = Field(default=None)
    causation_id: str | None = Field(default=None)
    producer: str | None = Field(default=None)
    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    headers_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    status: str = Field(default="pending", index=True)
    failed_consumer_name: str | None = Field(default=None, nullable=True, index=True)
    available_at: datetime = Field(default_factory=utc_now)
    locked_at: datetime | None = Field(default=None)
    lock_owner: str | None = Field(default=None, index=True)
    lock_expires_at: datetime | None = Field(default=None, index=True)
    attempt_count: int = Field(default=0)
    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    occurred_at: datetime = Field(default_factory=utc_now)
    created_at: datetime = Field(default_factory=utc_now)
    processed_at: datetime | None = Field(default=None)


class EventConsumerCheckpoint(SQLModel, table=True):
    """Idempotent consumption marker per (consumer_name, event_id)."""

    __tablename__ = "event_consumer_checkpoint"
    __table_args__ = (
        UniqueConstraint(
            "consumer_name",
            "event_id",
            name="uq_event_consumer_checkpoint_consumer_event",
        ),
        Index("ix_event_consumer_checkpoint_event_id", "event_id"),
    )

    id: str = Field(primary_key=True, default_factory=generate_checkpoint_id)
    consumer_name: str = Field(index=True)
    event_id: str = Field()
    processed_at: datetime = Field(default_factory=utc_now)
    result: str | None = Field(default=None)
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
