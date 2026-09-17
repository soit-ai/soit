"""Retention for the transport tables behind the transactional outbox.

`event_outbox` rows that were dispatched and `event_consumer_checkpoint` rows
older than the retention window are deleted in batches. Failed rows are kept:
they are replayed by hand, and a purge would erase the evidence of the
failure. Governance evidence (runs, steps, cost entries, audit) is never
touched here.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.events import EventConsumerCheckpoint, EventOutbox

logger = logging.getLogger(__name__)

DISPATCHED_OUTBOX_STATUS = "done"


@dataclass(frozen=True)
class RetentionOutcome:
    """Rows removed by one purge pass."""

    outbox_rows: int
    checkpoint_rows: int


async def purge_dispatched_outbox(
    db: AsyncSession,
    *,
    older_than: datetime,
    batch_size: int = 1000,
) -> int:
    """Delete dispatched outbox rows processed before `older_than`, batch by batch."""
    removed = 0
    while True:
        ids = list(
            (
                await db.exec(
                    select(EventOutbox.id)
                    .where(
                        EventOutbox.status == DISPATCHED_OUTBOX_STATUS,
                        EventOutbox.processed_at.is_not(None),
                        EventOutbox.processed_at < older_than,
                    )
                    .limit(batch_size)
                )
            ).all()
        )
        if not ids:
            return removed
        await db.exec(delete(EventOutbox).where(EventOutbox.id.in_(ids)))
        await db.commit()
        removed += len(ids)
        if len(ids) < batch_size:
            return removed


async def purge_consumer_checkpoints(
    db: AsyncSession,
    *,
    older_than: datetime,
    batch_size: int = 1000,
) -> int:
    """Delete consumer checkpoints processed before `older_than`, batch by batch."""
    removed = 0
    while True:
        ids = list(
            (
                await db.exec(
                    select(EventConsumerCheckpoint.id)
                    .where(EventConsumerCheckpoint.processed_at < older_than)
                    .limit(batch_size)
                )
            ).all()
        )
        if not ids:
            return removed
        await db.exec(
            delete(EventConsumerCheckpoint).where(EventConsumerCheckpoint.id.in_(ids))
        )
        await db.commit()
        removed += len(ids)
        if len(ids) < batch_size:
            return removed


class OutboxRetentionService:
    """Periodic purge of the outbox transport tables."""

    def __init__(
        self,
        db_factory: Callable[[], AsyncSession],
        *,
        retention_days: int = 7,
        batch_size: int = 1000,
    ) -> None:
        if retention_days < 1:
            raise ValueError("retention_days must be at least 1")
        self.db_factory = db_factory
        self.retention_days = retention_days
        self.batch_size = max(1, batch_size)

    def cutoff(self, *, now: datetime | None = None) -> datetime:
        return (now or utc_now()) - timedelta(days=self.retention_days)

    async def purge_once(self, *, now: datetime | None = None) -> RetentionOutcome:
        """One purge pass on a fresh session."""
        older_than = self.cutoff(now=now)
        db = self.db_factory()
        try:
            outbox_rows = await purge_dispatched_outbox(
                db, older_than=older_than, batch_size=self.batch_size
            )
            checkpoint_rows = await purge_consumer_checkpoints(
                db, older_than=older_than, batch_size=self.batch_size
            )
        except Exception:
            await db.rollback()
            raise
        finally:
            await db.close()
        if outbox_rows or checkpoint_rows:
            logger.info(
                "outbox retention purged rows",
                extra={
                    "outbox_rows": outbox_rows,
                    "checkpoint_rows": checkpoint_rows,
                    "older_than": older_than.isoformat(),
                },
            )
        return RetentionOutcome(outbox_rows=outbox_rows, checkpoint_rows=checkpoint_rows)

    async def run_loop(self, *, interval_seconds: float = 3600.0) -> None:
        """Purge on an interval; a failed pass is logged and retried next time."""
        while True:
            try:
                await self.purge_once()
            except Exception:
                logger.exception("outbox retention pass failed")
            await asyncio.sleep(max(1.0, interval_seconds))
