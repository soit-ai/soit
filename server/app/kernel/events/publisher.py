"""Thin facade over OutboxRepository.enqueue (spec §4 publisher optional)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_models import EventOutbox
from app.kernel.events.outbox_repo import OutboxRepository


class OutboxPublisher:
    """Enqueue domain events in the caller's transaction."""

    def __init__(self, repo: OutboxRepository) -> None:
        self._repo = repo

    def publish(
        self,
        envelope: DomainEventEnvelope,
        *,
        row_id: Optional[str] = None,
        headers_json: Optional[dict[str, Any]] = None,
        available_at: Optional[datetime] = None,
    ) -> EventOutbox:
        """Delegate to repository (no commit)."""
        return self._repo.enqueue_from_envelope(
            envelope,
            row_id=row_id,
            headers_json=headers_json,
            available_at=available_at,
        )
