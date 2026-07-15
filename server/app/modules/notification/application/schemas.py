""" schemas

Notification domain schemas.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.kernel.contracts.notification import (
    NOTIFICATION_SEVERITY_INFO,
    NOTIFICATION_STATUS_UNREAD,
    NOTIFICATION_TYPE_SYSTEM,
)


class NotificationActionSchema(BaseModel):
    """Navigation action schema."""

    target: str | None = None
    route: str | None = None
    params: dict[str, Any] | None = None
    deeplink: str | None = None
    resource_ref: str | None = None


class NotificationCreate(BaseModel):
    """Create notification request."""

    title: str = Field(..., max_length=256)
    content: str | None = None
    type: str = Field(default=NOTIFICATION_TYPE_SYSTEM, max_length=64)
    severity: str | None = Field(default=NOTIFICATION_SEVERITY_INFO, max_length=32)
    source_module: str | None = Field(default=None, max_length=64)
    action: NotificationActionSchema | None = None
    meta: dict[str, Any] | None = None
    user_id: str | None = None


class NotificationResponse(BaseModel):
    """Notification response."""

    id: str
    tenant_id: str
    workspace_id: str
    user_id: str
    type: str
    severity: str | None
    status: str = Field(default=NOTIFICATION_STATUS_UNREAD)
    title: str
    content: str | None
    source_module: str | None
    action: dict[str, Any] | None
    meta: dict[str, Any] | None
    read_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationReadRequest(BaseModel):
    """Bulk mark-as-read request."""

    ids: list[str] | None = None
    all: bool = False


class NotificationUnreadCount(BaseModel):
    """Unread notification count response."""

    count: int


class NotificationBulkResult(BaseModel):
    """Bulk operation result."""

    updated: int


class NotificationPreferenceUpdate(BaseModel):
    """Editable per-user notification preferences."""

    delivery_mode: Literal["in_app", "in_app_email", "in_app_all"] = "in_app"
    categories: dict[str, bool] = Field(default_factory=dict)
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = Field(default="22:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    quiet_hours_end: str = Field(default="07:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = "UTC"


class NotificationPreferenceResponse(NotificationPreferenceUpdate):
    id: str
    created_at: datetime
    updated_at: datetime


class NotificationEndpointCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    kind: Literal["email", "webhook", "slack", "teams", "discord", "telegram", "other"]
    url: str = Field(min_length=1)


class NotificationEndpointUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    kind: Literal["email", "webhook", "slack", "teams", "discord", "telegram", "other"] | None = None
    url: str | None = Field(default=None, min_length=1)
    status: Literal["active", "disabled"] | None = None


class NotificationEndpointResponse(BaseModel):
    id: str
    name: str
    kind: str
    display_target: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationDeliveryResponse(BaseModel):
    id: str
    notification_id: str
    endpoint_id: str
    status: str
    attempt_count: int
    available_at: datetime
    last_error: str | None
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
