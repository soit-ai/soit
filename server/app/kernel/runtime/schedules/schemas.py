"""Public shapes for schedules."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScheduleCreate(BaseModel):
    """A new recurring trigger."""

    name: str = Field(min_length=1, max_length=128)
    target_kind: str = Field(min_length=1, max_length=32)
    """agent or workflow."""

    target_id: str = Field(min_length=1, max_length=128)
    cron: str = Field(min_length=1, max_length=128)
    timezone: str = Field(default="UTC", max_length=64)
    description: str | None = Field(default=None, max_length=512)
    inputs: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    catch_up: bool = False
    """Whether a missed occurrence runs late rather than being skipped."""


class ScheduleUpdate(BaseModel):
    """Changing a trigger. Omitted fields are left alone."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    cron: str | None = Field(default=None, min_length=1, max_length=128)
    timezone: str | None = Field(default=None, max_length=64)
    inputs: dict[str, Any] | None = None
    enabled: bool | None = None
    catch_up: bool | None = None


class ScheduleResponse(BaseModel):
    """A trigger, when it next fires, and how the last firing went."""

    id: str
    name: str
    description: str | None = None
    target_kind: str
    target_id: str
    inputs: dict[str, Any] = Field(default_factory=dict, validation_alias="input_json")
    cron: str
    timezone: str
    enabled: bool
    catch_up: bool
    next_fire_at: datetime | None = None
    last_fired_at: datetime | None = None
    last_run_id: str | None = None
    last_status: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator("next_fire_at", "last_fired_at", "created_at", "updated_at", mode="after")
    @classmethod
    def _as_utc(cls, value: datetime | None) -> datetime | None:
        """Present every moment in UTC, whether it came from the row or from memory.

        The database stores naive UTC; a value computed in this process is
        aware. Without this the same schedule would read with and without a
        ``Z`` depending on which path produced the response.
        """
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class SchedulePreviewRequest(BaseModel):
    """Check an expression before saving it."""

    cron: str = Field(min_length=1, max_length=128)
    timezone: str = Field(default="UTC", max_length=64)
    count: int = Field(default=5, ge=1, le=20)


class SchedulePreviewResponse(BaseModel):
    """The next few firings, in UTC."""

    fires_at: list[datetime]
