"""notification

Stable notification contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Any


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

    target: Optional[str] = None
    """Logical module or view target."""

    route: Optional[str] = None
    """Frontend route path (e.g., /knowledge/{knowledge_id})."""

    params: Optional[Dict[str, Any]] = None
    """Optional query/path params for client routing."""

    deeplink: Optional[str] = None
    """Optional absolute URL for deep linking."""

    resource_ref: Optional[str] = None
    """Stable resource ref (e.g., wf:xxx, knowledge:xxx)."""
