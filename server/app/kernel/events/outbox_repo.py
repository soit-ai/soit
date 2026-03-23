"""Repository for event_outbox rows (no implicit commit — caller owns transaction)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import and_, update
from sqlmodel import Session, select

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now
from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_models import EventOutbox


class OutboxRepository:
    """Enqueue and lifecycle helpers for outbox rows."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def enqueue_from_envelope(
        self,
        envelope: DomainEventEnvelope,
        *,
        row_id: Optional[str] = None,
        headers_json: Optional[dict[str, Any]] = None,
        available_at: Optional[datetime] = None,
    ) -> EventOutbox:
        """Stage a new outbox row (flush in same transaction as business writes)."""
        now = utc_now()
        row = EventOutbox(
            id=row_id if row_id is not None else generate_ulid(),
            event_id=envelope.event_id,
            event_type=envelope.event_type,
            event_version=envelope.event_version,
            tenant_id=envelope.tenant_id,
            subject_type=envelope.subject_type,
            subject_id=envelope.subject_id,
            run_id=envelope.run_id,
            task_id=envelope.task_id,
            thread_id=envelope.thread_id,
            workflow_run_id=envelope.workflow_run_id,
            correlation_id=envelope.correlation_id,
            causation_id=envelope.causation_id,
            producer=envelope.producer,
            payload_json=dict(envelope.payload),
            headers_json=headers_json,
            status="pending",
            available_at=available_at if available_at is not None else now,
            attempt_count=0,
            last_error=None,
            occurred_at=envelope.occurred_at,
            created_at=now,
            processed_at=None,
        )
        self.db.add(row)
        return row

    def list_pending_due(self, *, before: datetime, limit: int) -> list[EventOutbox]:
        """Pending rows ready for dispatch (available_at <= before)."""
        stmt = (
            select(EventOutbox)
            .where(
                and_(
                    EventOutbox.status == "pending",
                    EventOutbox.available_at <= before,
                )
            )
            .order_by(EventOutbox.available_at)
            .limit(limit)
        )
        return list(self.db.exec(stmt).all())

    def try_claim(self, row_id: str) -> bool:
        """Atomically move pending -> processing. Returns True if this worker claimed the row."""
        stmt = (
            update(EventOutbox)
            .where(
                and_(
                    EventOutbox.id == row_id,
                    EventOutbox.status == "pending",
                )
            )
            .values(status="processing")
        )
        result = self.db.exec(stmt)
        return int(result.rowcount or 0) == 1

    def get(self, row_id: str) -> Optional[EventOutbox]:
        """Load row by primary key."""
        return self.db.get(EventOutbox, row_id)

    def mark_done(self, row_id: str) -> None:
        """Mark successfully processed."""
        row = self.db.get(EventOutbox, row_id)
        if row is None:
            return
        row.status = "done"
        row.processed_at = utc_now()
        self.db.add(row)

    def mark_retry(self, row_id: str, error: str) -> None:
        """Return row to pending with backoff metadata (simple Phase-1 variant)."""
        row = self.db.get(EventOutbox, row_id)
        if row is None:
            return
        row.status = "pending"
        row.attempt_count = int(row.attempt_count or 0) + 1
        row.last_error = error
        row.available_at = utc_now()
        self.db.add(row)

    def mark_failed(self, row_id: str, error: str) -> None:
        """Terminal failure: stop retries (e.g. exceeded max attempts or poison message)."""
        row = self.db.get(EventOutbox, row_id)
        if row is None:
            return
        row.status = "failed"
        row.last_error = error
        row.processed_at = utc_now()
        self.db.add(row)
