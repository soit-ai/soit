"""Consumer checkpoint helpers for idempotent outbox handling."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.kernel.commons.time import utc_now
from app.kernel.events.outbox_models import EventConsumerCheckpoint


class ConsumerCheckpointRepository:
    """Persist (consumer_name, event_id) markers without breaking outer transactions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def is_processed(self, consumer_name: str, event_id: str) -> bool:
        """Return True if this consumer has already recorded success for the event."""
        stmt = select(EventConsumerCheckpoint.id).where(
            EventConsumerCheckpoint.consumer_name == consumer_name,
            EventConsumerCheckpoint.event_id == event_id,
        )
        return self.db.exec(stmt).first() is not None

    def try_record_success(
        self,
        consumer_name: str,
        event_id: str,
        *,
        result: Optional[str] = None,
        error_message: Optional[str] = None,
        processed_at: Optional[datetime] = None,
    ) -> bool:
        """Insert checkpoint row; return True if inserted, False if duplicate (idempotent skip).

        Uses a savepoint so IntegrityError does not abort the caller's entire transaction.
        """
        row = EventConsumerCheckpoint(
            consumer_name=consumer_name,
            event_id=event_id,
            result=result,
            error_message=error_message,
            processed_at=processed_at if processed_at is not None else utc_now(),
        )
        try:
            with self.db.begin_nested():
                self.db.add(row)
                self.db.flush()
            return True
        except IntegrityError:
            return False
