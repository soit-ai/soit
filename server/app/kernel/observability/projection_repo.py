"""Helpers for idempotent observability consumer side-effects (Wave C)."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.kernel.commons.ids import generate_ulid
from app.kernel.observability.projection_models import ObservabilityProjectionRecord


def try_claim_projection_slot(db: Session, *, consumer_name: str, event_id: str) -> bool:
    """Insert dedupe row; return True if this consumer owns first apply for event_id.

    Uses a savepoint so IntegrityError does not abort the outer dispatcher session.
    """
    try:
        with db.begin_nested():
            db.add(
                ObservabilityProjectionRecord(
                    id=generate_ulid(),
                    consumer_name=consumer_name,
                    event_id=event_id,
                )
            )
            db.flush()
        return True
    except IntegrityError:
        return False
