"""Outbox handler for run.created (Phase 1 placeholder for downstream execution)."""

from __future__ import annotations

from sqlmodel import Session

from app.kernel.events.outbox_models import EventOutbox


def handle_run_created_outbox(_db: Session, _row: EventOutbox) -> None:
    """Acknowledge run.created; extend with execution scheduling in later Wave B tasks."""
    return None
