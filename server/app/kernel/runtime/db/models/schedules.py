"""Scheduled triggers: what to run, when, and what happened last time."""

from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime
from sqlmodel import JSON, Field, Index, SQLModel, UniqueConstraint

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


def generate_schedule_id() -> str:
    """Generate a schedule ID."""
    return f"sch_{generate_ulid()}"


class Schedule(SQLModel, table=True):
    """A recurring trigger for an agent or a workflow.

    The schedule owns when; it does not own how. Firing hands the work to the
    same durable path the API uses, so a scheduled run is an ordinary run --
    same ledger, same evidence, same recovery -- distinguishable only by what
    started it.

    Lease columns are here because the scheduler claims a due schedule the way
    every other durable worker claims work: several replicas may be running,
    and exactly one of them must fire each occurrence.
    """

    __tablename__ = "schedules"
    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_schedule_name"),
        Index("ix_schedules_due", "status", "enabled", "next_fire_at"),
        Index("ix_schedules_scope", "tenant_id", "workspace_id"),
    )

    id: str = Field(primary_key=True, default_factory=generate_schedule_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)

    name: str = Field(max_length=128)
    description: str | None = Field(default=None, nullable=True, max_length=512)

    target_kind: str = Field(index=True, max_length=32)
    """agent or workflow."""

    target_id: str = Field(index=True, max_length=128)
    input_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """What to send the target. Shape depends on the kind."""

    cron: str = Field(max_length=128)
    timezone: str = Field(default="UTC", max_length=64)
    """Matching happens in this zone, so a daily time keeps its local hour."""

    catch_up: bool = Field(default=False)
    """Whether a missed occurrence runs late.

    Off by default: a scheduler that was down for a day would otherwise wake up
    and fire twenty-four hourly jobs at once, which is rarely what anyone
    wanted from "hourly".
    """

    enabled: bool = Field(default=True, index=True)

    next_fire_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
    )
    last_fired_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_run_id: str | None = Field(default=None, nullable=True, index=True)
    last_status: str | None = Field(default=None, nullable=True, max_length=32)
    last_error: str | None = Field(default=None, nullable=True, max_length=512)

    # Claim state, shared with every other durable worker.
    status: str = Field(default="queued", index=True)
    lease_owner: str | None = Field(default=None, index=True)
    lease_expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
    )
    attempt_count: int = Field(default=0)

    created_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
