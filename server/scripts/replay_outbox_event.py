"""Replay one terminally failed outbox event by event id."""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlmodel import select

from app.infra.db.session import get_async_session_local
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.runtime.db.models.events import EventOutbox


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Return one failed outbox event to the pending queue."
    )
    parser.add_argument("event_id", help="Stable domain event id to replay")
    args = parser.parse_args()

    db = get_async_session_local()()
    try:
        row = (
            await db.exec(select(EventOutbox).where(EventOutbox.event_id == args.event_id))
        ).first()
        if row is None:
            parser.error(f"Outbox event not found: {args.event_id}")
        if not await OutboxRepository(db).replay_failed(row.id):
            parser.error(f"Outbox event is not in failed state: {args.event_id}")
        await db.commit()
        print(f"Queued outbox event for replay: {args.event_id}")
        return 0
    except Exception:
        await db.rollback()
        raise
    finally:
        await db.close()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(main()))
