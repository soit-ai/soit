"""Outbox consumers for task.* events (Wave B2 placeholder)."""

from __future__ import annotations

from sqlmodel import Session

from app.kernel.runtime.db.models.events import EventOutbox


def handle_task_runtime_outbox(_db: Session, _row: EventOutbox) -> None:
    """Reserved for task execution side-effects; observe migrates in Wave C."""
    return None
