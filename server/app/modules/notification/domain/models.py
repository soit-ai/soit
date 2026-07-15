""" models

Notification domain model.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import Text
from sqlmodel import JSON, Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


class Notification(SQLModel, table=True):
    """Notification model for user inbox."""

    __tablename__ = "notifications"

    id: str = Field(primary_key=True)
    """Notification ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    user_id: str = Field(index=True)
    """Recipient user ID."""

    type: str = Field(index=True, max_length=64)
    """Notification type (system, message, alert, reminder, custom)."""

    severity: str | None = Field(default=None, index=True, max_length=32)
    """Severity level (info, warning, error, success)."""

    status: str = Field(default="unread", index=True, max_length=32)
    """Status (unread, read, archived)."""

    title: str = Field(max_length=256)
    """Notification title."""

    content: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    """Notification content/body."""

    source_module: str | None = Field(default=None, index=True, max_length=64)
    """Source module (workflow, knowledge, modelhub, etc.)."""

    action: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Navigation action payload."""

    meta: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Additional metadata for future extensions."""

    read_at: datetime | None = Field(default=None, nullable=True)
    """Read timestamp."""

    archived_at: datetime | None = Field(default=None, nullable=True)
    """Archived timestamp."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Update timestamp."""


class NotificationPreference(SQLModel, table=True):
    """Per-user outbound notification preferences."""

    __tablename__ = "notification_preferences"

    id: str = Field(primary_key=True, default_factory=lambda: f"npref_{generate_ulid()}")
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    user_id: str = Field(index=True)
    delivery_mode: str = Field(default="in_app", max_length=32)
    categories_json: dict[str, bool] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    quiet_hours_enabled: bool = Field(default=False)
    quiet_hours_start: str = Field(default="22:00", max_length=5)
    quiet_hours_end: str = Field(default="07:00", max_length=5)
    timezone: str = Field(default="UTC", max_length=64)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class NotificationEndpoint(SQLModel, table=True):
    """Secret-backed Apprise destination owned by a user."""

    __tablename__ = "notification_endpoints"

    id: str = Field(primary_key=True, default_factory=lambda: f"nep_{generate_ulid()}")
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    user_id: str = Field(index=True)
    name: str = Field(max_length=128)
    kind: str = Field(index=True, max_length=32)
    secret_ref: str = Field(max_length=256)
    display_target: str = Field(max_length=256)
    status: str = Field(default="active", index=True, max_length=32)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class NotificationDelivery(SQLModel, table=True):
    """Outbound delivery state; references are enforced in application code."""

    __tablename__ = "notification_deliveries"

    id: str = Field(primary_key=True, default_factory=lambda: f"ndel_{generate_ulid()}")
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    user_id: str = Field(index=True)
    notification_id: str = Field(index=True)
    endpoint_id: str = Field(index=True)
    status: str = Field(default="queued", index=True, max_length=32)
    attempt_count: int = Field(default=0)
    available_at: datetime = Field(default_factory=utc_now, index=True)
    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    sent_at: datetime | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
