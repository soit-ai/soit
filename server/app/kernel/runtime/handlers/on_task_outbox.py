"""Outbox consumers for task.* events (Wave B2 placeholder)."""

from __future__ import annotations

from sqlmodel import Session

from app.kernel.events.outbox_models import EventOutbox


def handle_task_runtime_outbox(_db: Session, _row: EventOutbox) -> None:
    """Reserved for task execution side-effects; observability migrates in Wave C."""
    return None
