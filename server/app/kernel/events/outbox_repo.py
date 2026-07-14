"""Repository for event_outbox rows (no implicit commit — caller owns transaction)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, update
from sqlmodel import Session, select

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now
from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.runtime.db.models.events import EventOutbox


@dataclass(frozen=True, slots=True)
class OutboxOperationalStats:
    """Small operational snapshot exported by the dispatcher process."""

    pending_count: int
    retry_count: int
    failed_count: int
    oldest_pending_at: datetime | None


class OutboxRepository:
    """Enqueue and lifecycle helpers for outbox rows."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def enqueue_from_envelope(
        self,
        envelope: DomainEventEnvelope,
        *,
        row_id: str | None = None,
        headers_json: dict[str, Any] | None = None,
        available_at: datetime | None = None,
    ) -> EventOutbox:
        """Stage a new outbox row (flush in same transaction as business writes)."""
        now = utc_now()
        row = EventOutbox(
            id=row_id if row_id is not None else generate_ulid(),
            event_id=envelope.event_id,
            event_type=envelope.event_type,
            event_version=envelope.event_version,
            tenant_id=envelope.tenant_id,
            workspace_id=envelope.workspace_id,
            idempotency_key=envelope.idempotency_key or envelope.event_id,
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
            failed_consumer_name=None,
            available_at=available_at if available_at is not None else now,
            locked_at=None,
            lock_owner=None,
            lock_expires_at=None,
            attempt_count=0,
            last_error=None,
            occurred_at=envelope.occurred_at,
            created_at=now,
            processed_at=None,
        )
        self.db.add(row)
        return row

    def list_pending_due(self, *, before: datetime, limit: int) -> list[EventOutbox]:
        """Rows ready for dispatch, including abandoned rows with expired leases."""
        stmt = (
            select(EventOutbox)
            .where(
                or_(
                    and_(
                        EventOutbox.status == "pending",
                        EventOutbox.available_at <= before,
                    ),
                    and_(
                        EventOutbox.status == "processing",
                        EventOutbox.lock_expires_at.is_not(None),
                        EventOutbox.lock_expires_at <= before,
                    ),
                )
            )
            .order_by(EventOutbox.available_at)
            .limit(limit)
        )
        return list(self.db.exec(stmt).all())

    def try_claim(
        self,
        row_id: str,
        *,
        owner: str = "outbox-dispatcher",
        now: datetime | None = None,
        lease_seconds: int = 60,
    ) -> bool:
        """Atomically acquire a bounded lease for a due or abandoned row."""
        claimed_at = now if now is not None else utc_now()
        stmt = (
            update(EventOutbox)
            .where(
                and_(
                    EventOutbox.id == row_id,
                    or_(
                        and_(
                            EventOutbox.status == "pending",
                            EventOutbox.available_at <= claimed_at,
                        ),
                        and_(
                            EventOutbox.status == "processing",
                            EventOutbox.lock_expires_at.is_not(None),
                            EventOutbox.lock_expires_at <= claimed_at,
                        ),
                    ),
                )
            )
            .values(
                status="processing",
                locked_at=claimed_at,
                lock_owner=owner,
                lock_expires_at=claimed_at + timedelta(seconds=max(1, lease_seconds)),
            )
        )
        result = self.db.exec(stmt.execution_options(synchronize_session=False))
        self.db.expire_all()
        return int(result.rowcount or 0) == 1

    def get(self, row_id: str) -> EventOutbox | None:
        """Load row by primary key."""
        return self.db.get(EventOutbox, row_id)

    def get_operational_stats(self) -> OutboxOperationalStats:
        """Return backlog and failure signals without loading event payloads."""
        pending_count = self.db.exec(
            select(func.count())
            .select_from(EventOutbox)
            .where(EventOutbox.status == "pending")
        ).one()
        retry_count = self.db.exec(
            select(func.count())
            .select_from(EventOutbox)
            .where(
                and_(
                    EventOutbox.status == "pending",
                    EventOutbox.attempt_count > 0,
                )
            )
        ).one()
        failed_count = self.db.exec(
            select(func.count())
            .select_from(EventOutbox)
            .where(EventOutbox.status == "failed")
        ).one()
        oldest_pending_at = self.db.exec(
            select(func.min(EventOutbox.created_at)).where(
                EventOutbox.status == "pending"
            )
        ).one()
        return OutboxOperationalStats(
            pending_count=int(pending_count),
            retry_count=int(retry_count),
            failed_count=int(failed_count),
            oldest_pending_at=oldest_pending_at,
        )

    def mark_done(self, row_id: str) -> None:
        """Mark successfully processed."""
        row = self.db.get(EventOutbox, row_id)
        if row is None:
            return
        row.status = "done"
        row.processed_at = utc_now()
        row.locked_at = None
        row.lock_owner = None
        row.lock_expires_at = None
        self.db.add(row)

    def mark_retry(
        self,
        row_id: str,
        error: str,
        *,
        now: datetime | None = None,
        base_delay_seconds: int = 1,
        max_delay_seconds: int = 300,
    ) -> None:
        """Return a row to pending with bounded exponential backoff."""
        row = self.db.get(EventOutbox, row_id)
        if row is None:
            return
        retry_at = now if now is not None else utc_now()
        row.status = "pending"
        row.attempt_count = int(row.attempt_count or 0) + 1
        row.last_error = error
        delay = min(
            max(1, max_delay_seconds),
            max(1, base_delay_seconds) * (2 ** max(0, row.attempt_count - 1)),
        )
        row.available_at = retry_at + timedelta(seconds=delay)
        row.locked_at = None
        row.lock_owner = None
        row.lock_expires_at = None
        self.db.add(row)

    def mark_failed(self, row_id: str, error: str, *, consumer_name: str | None = None) -> None:
        """Terminal failure: stop retries (e.g. exceeded max attempts or poison message)."""
        row = self.db.get(EventOutbox, row_id)
        if row is None:
            return
        row.status = "failed"
        row.failed_consumer_name = consumer_name
        row.last_error = error
        row.processed_at = utc_now()
        row.locked_at = None
        row.lock_owner = None
        row.lock_expires_at = None
        self.db.add(row)

    def replay_failed(self, row_id: str, *, now: datetime | None = None) -> bool:
        """Atomically return one terminally failed row to the pending queue."""
        replay_at = now if now is not None else utc_now()
        stmt = (
            update(EventOutbox)
            .where(
                and_(
                    EventOutbox.id == row_id,
                    EventOutbox.status == "failed",
                )
            )
            .values(
                status="pending",
                failed_consumer_name=None,
                available_at=replay_at,
                attempt_count=0,
                processed_at=None,
                locked_at=None,
                lock_owner=None,
                lock_expires_at=None,
            )
        )
        result = self.db.exec(stmt.execution_options(synchronize_session=False))
        self.db.expire_all()
        return int(result.rowcount or 0) == 1
