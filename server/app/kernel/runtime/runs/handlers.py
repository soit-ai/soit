"""Outbox handlers for run events."""

from __future__ import annotations

from sqlmodel import Session

from app.kernel.runtime.db.models.events import EventOutbox


def handle_run_created_outbox(_db: Session, _row: EventOutbox) -> None:
    """Acknowledge run.created; extend with execution scheduling in later waves."""

    return None
