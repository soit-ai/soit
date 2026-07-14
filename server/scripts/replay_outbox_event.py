"""Replay one terminally failed outbox event by event id."""

from __future__ import annotations

import argparse

from sqlmodel import select

from app.infra.db.session import get_db_sync
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.runtime.db.models.events import EventOutbox


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Return one failed outbox event to the pending queue."
    )
    parser.add_argument("event_id", help="Stable domain event id to replay")
    args = parser.parse_args()

    db = get_db_sync()
    try:
        row = db.exec(
            select(EventOutbox).where(EventOutbox.event_id == args.event_id)
        ).first()
        if row is None:
            parser.error(f"Outbox event not found: {args.event_id}")
        if not OutboxRepository(db).replay_failed(row.id):
            parser.error(f"Outbox event is not in failed state: {args.event_id}")
        db.commit()
        print(f"Queued outbox event for replay: {args.event_id}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
