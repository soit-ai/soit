""" schemas

Notification domain schemas.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

from app.kernel.contracts.notification import (
    NOTIFICATION_TYPE_SYSTEM,
    NOTIFICATION_SEVERITY_INFO,
    NOTIFICATION_STATUS_UNREAD,
)


class NotificationActionSchema(BaseModel):
    """Navigation action schema."""

    target: Optional[str] = None
    route: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    deeplink: Optional[str] = None
    resource_ref: Optional[str] = None


class NotificationCreate(BaseModel):
    """Create notification request."""

    title: str = Field(..., max_length=256)
    content: Optional[str] = None
    type: str = Field(default=NOTIFICATION_TYPE_SYSTEM, max_length=64)
    severity: Optional[str] = Field(default=NOTIFICATION_SEVERITY_INFO, max_length=32)
    source_module: Optional[str] = Field(default=None, max_length=64)
    action: Optional[NotificationActionSchema] = None
    meta: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None


class NotificationResponse(BaseModel):
    """Notification response."""

    id: str
    tenant_id: str
    workspace_id: str
    user_id: str
    type: str
    severity: Optional[str]
    status: str = Field(default=NOTIFICATION_STATUS_UNREAD)
    title: str
    content: Optional[str]
    source_module: Optional[str]
    action: Optional[Dict[str, Any]]
    meta: Optional[Dict[str, Any]]
    read_at: Optional[datetime]
    archived_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationReadRequest(BaseModel):
    """Bulk mark-as-read request."""

    ids: Optional[List[str]] = None
    all: bool = False


class NotificationUnreadCount(BaseModel):
    """Unread notification count response."""

    count: int


class NotificationBulkResult(BaseModel):
    """Bulk operation result."""

    updated: int
