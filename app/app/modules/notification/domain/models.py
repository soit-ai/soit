""" models

Notification domain model.
"""

from typing import Optional, Dict, Any
from datetime import datetime

from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import Text

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

    severity: Optional[str] = Field(default=None, index=True, max_length=32)
    """Severity level (info, warning, error, success)."""

    status: str = Field(default="unread", index=True, max_length=32)
    """Status (unread, read, archived)."""

    title: str = Field(max_length=256)
    """Notification title."""

    content: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    """Notification content/body."""

    source_module: Optional[str] = Field(default=None, index=True, max_length=64)
    """Source module (workflow, knowledge, modelhub, etc.)."""

    action: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Navigation action payload."""

    meta: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Additional metadata for future extensions."""

    read_at: Optional[datetime] = Field(default=None, nullable=True)
    """Read timestamp."""

    archived_at: Optional[datetime] = Field(default=None, nullable=True)
    """Archived timestamp."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Update timestamp."""
