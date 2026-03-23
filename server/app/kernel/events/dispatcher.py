"""Outbox dispatcher: claim rows, run registered handlers with checkpoint idempotency."""

from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import datetime
from typing import Any, Callable, Optional

from sqlmodel import Session

from app.kernel.commons.time import utc_now
from app.kernel.events.checkpoint import ConsumerCheckpointRepository
from app.kernel.events.outbox_models import DeadLetterEvent, EventOutbox
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.registry import OutboxHandlerRegistry

logger = logging.getLogger(__name__)

OutboxHandlerFn = Callable[[Session, EventOutbox], Any]


class OutboxDispatcher:
    """Implements checklist §10: claim → per-handler checkpoint → done / retry / failed."""

    def __init__(
        self,
        db: Session,
        registry: OutboxHandlerRegistry,
        *,
        max_dispatch_attempts: int = 64,
        record_dead_letter: bool = True,
    ) -> None:
        self.db = db
        self.registry = registry
        self.repo = OutboxRepository(db)
        self.checkpoints = ConsumerCheckpointRepository(db)
        self.max_dispatch_attempts = max_dispatch_attempts
        self.record_dead_letter = record_dead_letter

    async def _invoke(self, handler: OutboxHandlerFn, row: EventOutbox) -> None:
        result = handler(self.db, row)
        if inspect.isawaitable(result):
            await result  # type: ignore[func-returns-value]

    def _insert_dead_letter(self, row: EventOutbox, consumer_name: str, message: str) -> None:
        if not self.record_dead_letter:
            return
        self.db.add(
            DeadLetterEvent(
                event_id=row.event_id,
                event_type=row.event_type,
                consumer_name=consumer_name,
                payload_json=dict(row.payload_json or {}),
                error_message=message,
            )
        )

    def _on_handler_error(self, row_id: str, consumer_name: str, exc: BaseException) -> None:
        row_fresh = self.repo.get(row_id)
        if row_fresh is None:
            return
        msg = f"{consumer_name}: {exc}"
        next_attempt = int(row_fresh.attempt_count or 0) + 1
        if next_attempt >= self.max_dispatch_attempts:
            self.repo.mark_failed(row_id, msg)
            self._insert_dead_letter(row_fresh, consumer_name, str(exc))
            logger.warning(
                "outbox row %s terminal failure after %s attempts: %s",
                row_id,
                next_attempt,
                msg,
            )
        else:
            self.repo.mark_retry(row_id, msg)

    async def dispatch_row(self, row: EventOutbox) -> bool:
        """Try to claim and fully process one row. Returns True if this worker owned dispatch."""
        if not self.repo.try_claim(row.id):
            return False

        handlers = self.registry.get_handlers(row.event_type)
        if not handlers:
            self.repo.mark_done(row.id)
            return True

        for reg in handlers:
            if self.checkpoints.is_processed(reg.consumer_name, row.event_id):
                continue
            try:
                await self._invoke(reg.handler, row)
            except Exception as exc:  # noqa: BLE001 — surface to outbox retry/DLQ
                self._on_handler_error(row.id, reg.consumer_name, exc)
                return True
            self.checkpoints.try_record_success(reg.consumer_name, row.event_id)

        self.repo.mark_done(row.id)
        return True

    async def run_once(
        self,
        *,
        before: Optional[datetime] = None,
        batch_limit: int = 50,
    ) -> int:
        """Process up to `batch_limit` due pending rows; returns how many were claimed for work."""
        cutoff = before if before is not None else utc_now()
        rows = self.repo.list_pending_due(before=cutoff, limit=batch_limit)
        attempted = 0
        for row in rows:
            if await self.dispatch_row(row):
                attempted += 1
        return attempted


class OutboxDispatcherService:
    """Runs dispatcher ticks with a fresh DB session per tick (API background worker)."""

    def __init__(
        self,
        registry: OutboxHandlerRegistry,
        *,
        db_factory: Callable[[], Session],
        max_dispatch_attempts: int = 64,
        record_dead_letter: bool = True,
        batch_limit: int = 50,
    ) -> None:
        self.registry = registry
        self.db_factory = db_factory
        self.max_dispatch_attempts = max_dispatch_attempts
        self.record_dead_letter = record_dead_letter
        self.batch_limit = batch_limit

    async def run_once(self) -> int:
        """One poll: claim/process batch and commit."""
        db = self.db_factory()
        try:
            disp = OutboxDispatcher(
                db,
                self.registry,
                max_dispatch_attempts=self.max_dispatch_attempts,
                record_dead_letter=self.record_dead_letter,
            )
            n = await disp.run_once(batch_limit=self.batch_limit)
            db.commit()
            return n
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def run_loop(self, *, poll_interval_seconds: float = 1.0) -> None:
        """Infinite background loop; swallow tick errors so the worker stays alive."""
        while True:
            try:
                await self.run_once()
            except Exception:
                logger.exception("outbox dispatcher tick failed")
            await asyncio.sleep(max(0.05, poll_interval_seconds))
