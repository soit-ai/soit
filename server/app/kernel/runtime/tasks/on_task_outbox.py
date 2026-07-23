"""Core runtime acknowledgements for task lifecycle outbox events."""

from __future__ import annotations

from sqlmodel import Session

from app.kernel.runtime.db.models.events import EventOutbox


def handle_task_runtime_outbox(_db: Session, _row: EventOutbox) -> None:
    """Acknowledge core delivery; separate handlers build observe projections."""
    return None
