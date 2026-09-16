"""Outbox handlers for run events."""

from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.runtime.db.models.events import EventOutbox


async def handle_run_created_outbox(_db: AsyncSession, _row: EventOutbox) -> None:
    """Acknowledge run.created; extend with execution scheduling in later waves."""

    return None
