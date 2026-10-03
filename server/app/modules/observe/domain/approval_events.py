"""Approval domain event type constants for transactional outbox (B4)."""


class ApprovalEventType:
    """Event types emitted with approval lifecycle writes."""

    REQUESTED = "approval.requested"
    APPROVED = "approval.approved"
    REJECTED = "approval.rejected"
    CANCELED = "approval.canceled"
    EXPIRED = "approval.expired"
    DELEGATED = "approval.delegated"
    DUE_SOON = "approval.due_soon"
