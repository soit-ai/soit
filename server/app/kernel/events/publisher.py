"""Thin facade over OutboxRepository.enqueue (spec §4 publisher optional)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from opentelemetry.propagate import inject

from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.payload_registry import get_event_payload_version
from app.kernel.runtime.db.models.events import EventOutbox


class OutboxPublisher:
    """Enqueue domain events in the caller's transaction."""

    def __init__(self, repo: OutboxRepository) -> None:
        self._repo = repo

    def publish(
        self,
        envelope: DomainEventEnvelope,
        *,
        row_id: str | None = None,
        headers_json: dict[str, Any] | None = None,
        available_at: datetime | None = None,
    ) -> EventOutbox:
        """Delegate to repository (no commit)."""
        envelope = envelope.model_copy(
            update={
                "event_version": get_event_payload_version(envelope.event_type, envelope.event_version),
            }
        )
        propagated_headers = dict(headers_json or {})
        inject(propagated_headers)
        if envelope.tenant_id:
            propagated_headers.setdefault("tenant_id", envelope.tenant_id)
        if envelope.workspace_id:
            propagated_headers.setdefault("workspace_id", envelope.workspace_id)
        if envelope.correlation_id:
            propagated_headers.setdefault("correlation_id", envelope.correlation_id)
        return self._repo.enqueue_from_envelope(
            envelope,
            row_id=row_id,
            headers_json=propagated_headers or None,
            available_at=available_at,
        )
