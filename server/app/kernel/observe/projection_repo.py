"""Helpers for idempotent observe consumer side-effects."""

from __future__ import annotations

from sqlmodel import Session

from app.kernel.events.checkpoint import try_claim_consumer_slot


def try_claim_projection_slot(db: Session, *, consumer_name: str, event_id: str) -> bool:
    """Claim the observe side-effect slot in the unified consumer checkpoint table."""
    return try_claim_consumer_slot(
        db,
        consumer_name=consumer_name,
        event_id=event_id,
        result="observe_projection",
    )
