"""Persistence models for transactional outbox (aligned with migration 20260323100000)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

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


def generate_dead_letter_id() -> str:
    """Primary key for dead letter rows."""

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
    tenant_id: Optional[str] = Field(default=None, index=True)
    subject_type: Optional[str] = Field(default=None)
    subject_id: Optional[str] = Field(default=None)
    run_id: Optional[str] = Field(default=None)
    task_id: Optional[str] = Field(default=None)
    thread_id: Optional[str] = Field(default=None)
    workflow_run_id: Optional[str] = Field(default=None)
    correlation_id: Optional[str] = Field(default=None)
    causation_id: Optional[str] = Field(default=None)
    producer: Optional[str] = Field(default=None)
    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    headers_json: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    status: str = Field(default="pending", index=True)
    available_at: datetime = Field(default_factory=utc_now)
    attempt_count: int = Field(default=0)
    last_error: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    occurred_at: datetime = Field(default_factory=utc_now)
    created_at: datetime = Field(default_factory=utc_now)
    processed_at: Optional[datetime] = Field(default=None)


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
    result: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))


class DeadLetterEvent(SQLModel, table=True):
    """Permanently failed consumer attempts (optional operational table)."""

    __tablename__ = "dead_letter_events"
    __table_args__ = (Index("ix_dead_letter_events_event_id", "event_id"),)

    id: str = Field(primary_key=True, default_factory=generate_dead_letter_id)
    event_id: str = Field()
    event_type: str = Field()
    consumer_name: str = Field()
    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    failed_at: datetime = Field(default_factory=utc_now)
