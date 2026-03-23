"""DB-backed idempotency markers for observability outbox consumers (Wave C3/C4)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


def generate_projection_record_id() -> str:
    return generate_ulid()


class ObservabilityProjectionRecord(SQLModel, table=True):
    """One row per (consumer_name, event_id) successful projection apply."""

    __tablename__ = "observability_projection_records"
    __table_args__ = (
        UniqueConstraint(
            "consumer_name",
            "event_id",
            name="uq_observability_projection_consumer_event",
        ),
    )

    id: str = Field(primary_key=True, default_factory=generate_projection_record_id)
    consumer_name: str = Field(index=True)
    event_id: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now)
