"""notification

Stable notification contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

NOTIFICATION_TYPE_SYSTEM = "system"
NOTIFICATION_TYPE_MESSAGE = "message"
NOTIFICATION_TYPE_ALERT = "alert"
NOTIFICATION_TYPE_REMINDER = "reminder"
NOTIFICATION_TYPE_CUSTOM = "custom"

NOTIFICATION_SEVERITY_INFO = "info"
NOTIFICATION_SEVERITY_WARNING = "warning"
NOTIFICATION_SEVERITY_ERROR = "error"
NOTIFICATION_SEVERITY_SUCCESS = "success"

NOTIFICATION_STATUS_UNREAD = "unread"
NOTIFICATION_STATUS_READ = "read"
NOTIFICATION_STATUS_ARCHIVED = "archived"


@dataclass(frozen=True)
class NotificationAction:
    """Action target for notification routing."""

    target: str | None = None
    """Logical module or view target."""

    route: str | None = None
    """Frontend route path (e.g., /knowledge/{knowledge_id})."""

    params: dict[str, Any] | None = None
    """Optional query/path params for client routing."""

    deeplink: str | None = None
    """Optional absolute URL for deep linking."""

    resource_ref: str | None = None
    """Stable resource ref (e.g., wf:xxx, knowledge:xxx)."""
