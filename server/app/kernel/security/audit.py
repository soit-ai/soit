""" audit

Audit event definitions and sinks.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from app.kernel.contracts.context import RequestContext
from app.kernel.commons.time import utc_now


class AuditEvent:
    """Audit event."""
    
    def __init__(
        self,
        event_type: str,
        ctx: RequestContext,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize audit event.
        
        Args:
            event_type: Event type (create, update, delete, access, etc.).
            ctx: Request context.
            resource_type: Resource type (run, workflow, knowledge, etc.).
            resource_id: Resource ID.
            action: Action performed.
            details: Optional additional details.
        """
        self.event_type = event_type
        self.tenant_id = ctx.tenant_id
        self.workspace_id = ctx.workspace_id
        self.user_id = ctx.user_id
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.action = action
        self.details = details or {}
        self.timestamp = utc_now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "event_type": self.event_type,
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class AuditLogger:
    """Audit logger (writes to structured logs)."""
    
    def log(self, event: AuditEvent) -> None:
        """Log audit event.
        
        Args:
            event: Audit event to log.
        """
        # In production, write to audit log (separate table or log file)
        # For now, use structured logging
        import logging
        logger = logging.getLogger("audit")
        logger.info("audit_event", extra=event.to_dict())


# Global audit logger instance
audit_logger = AuditLogger()


def log_audit_event(
    event_type: str,
    ctx: RequestContext,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    action: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Log an audit event.
    
    Args:
        event_type: Event type.
        ctx: Request context.
        resource_type: Resource type.
        resource_id: Resource ID.
        action: Action performed.
        details: Optional details.
    """
    event = AuditEvent(
        event_type=event_type,
        ctx=ctx,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        details=details,
    )
    audit_logger.log(event)
