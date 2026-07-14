"""Outbox dispatcher: claim rows, run registered handlers with checkpoint idempotency."""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import socket
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.trace import SpanKind, Tracer
from sqlmodel import Session

from app.kernel.commons.time import utc_now
from app.kernel.events.checkpoint import ConsumerCheckpointRepository
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.payload_registry import validate_event_payload_version
from app.kernel.events.registry import OutboxHandlerRegistry
from app.kernel.observe.metrics import (
    outbox_dead_letters,
    outbox_delivery_latency,
    outbox_dispatch_attempts,
    outbox_oldest_pending_age,
    outbox_pending,
    outbox_retries,
)
from app.kernel.runtime.db.models.events import EventOutbox

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
        worker_id: str = "outbox-dispatcher",
        lease_seconds: int = 60,
        tracer: Tracer | None = None,
    ) -> None:
        self.db = db
        self.registry = registry
        self.repo = OutboxRepository(db)
        self.checkpoints = ConsumerCheckpointRepository(db)
        self.max_dispatch_attempts = max_dispatch_attempts
        self.record_dead_letter = record_dead_letter
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.tracer = tracer or trace.get_tracer("soit.outbox.dispatcher")

    async def _invoke(self, handler: OutboxHandlerFn, row: EventOutbox) -> None:
        result = handler(self.db, row)
        if inspect.isawaitable(result):
            await result

    def _on_handler_error(self, row_id: str, consumer_name: str, exc: BaseException) -> None:
        row_fresh = self.repo.get(row_id)
        if row_fresh is None:
            return
        msg = f"{consumer_name}: {exc}"
        next_attempt = int(row_fresh.attempt_count or 0) + 1
        if next_attempt >= self.max_dispatch_attempts:
            self.repo.mark_failed(row_id, msg, consumer_name=consumer_name)
            outbox_dispatch_attempts.labels(outcome="failed").inc()
            logger.warning(
                "outbox row %s terminal failure after %s attempts: %s",
                row_id,
                next_attempt,
                msg,
            )
        else:
            self.repo.mark_retry(row_id, msg)
            outbox_dispatch_attempts.labels(outcome="retry").inc()

    async def dispatch_row(self, row: EventOutbox) -> bool:
        """Try to claim and fully process one row. Returns True if this worker owned dispatch."""
        if not self.repo.try_claim(
            row.id,
            owner=self.worker_id,
            lease_seconds=self.lease_seconds,
        ):
            return False

        parent_context = extract(row.headers_json or {})
        with self.tracer.start_as_current_span(
            f"outbox {row.event_type}",
            context=parent_context,
            kind=SpanKind.CONSUMER,
            attributes={
                "messaging.system": "soit.outbox",
                "messaging.operation.name": "process",
                "messaging.message.id": row.event_id,
                "soit.tenant_id": row.tenant_id or "",
                "soit.workspace_id": row.workspace_id or "",
                "soit.outbox.attempt": int(row.attempt_count or 0) + 1,
            },
        ):
            return await self._dispatch_claimed_row(row)

    async def _dispatch_claimed_row(self, row: EventOutbox) -> bool:
        """Process a row after its lease has been acquired."""

        try:
            validate_event_payload_version(row.event_type, row.event_version)
        except ValueError as exc:
            self.repo.mark_failed(row.id, str(exc))
            outbox_dispatch_attempts.labels(outcome="failed").inc()
            return True

        handlers = self.registry.get_handlers(row.event_type)
        if not handlers:
            self.repo.mark_done(row.id)
            self._record_success(row)
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
        self._record_success(row)
        return True

    @staticmethod
    def _record_success(row: EventOutbox) -> None:
        occurred_at = row.occurred_at
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=UTC)
        latency = max(0.0, (utc_now() - occurred_at).total_seconds())
        outbox_dispatch_attempts.labels(outcome="done").inc()
        outbox_delivery_latency.observe(latency)

    def update_operational_metrics(self) -> None:
        """Refresh current backlog gauges after a dispatcher tick."""
        stats = self.repo.get_operational_stats()
        outbox_pending.set(stats.pending_count)
        outbox_retries.set(stats.retry_count)
        outbox_dead_letters.set(stats.failed_count)
        oldest = stats.oldest_pending_at
        if oldest is None:
            outbox_oldest_pending_age.set(0)
            return
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=UTC)
        outbox_oldest_pending_age.set(max(0.0, (utc_now() - oldest).total_seconds()))

    async def run_once(
        self,
        *,
        before: datetime | None = None,
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
        lease_seconds: int = 60,
        worker_id: str | None = None,
    ) -> None:
        self.registry = registry
        self.db_factory = db_factory
        self.max_dispatch_attempts = max_dispatch_attempts
        self.record_dead_letter = record_dead_letter
        self.batch_limit = batch_limit
        self.lease_seconds = lease_seconds
        self.worker_id = worker_id or (
            f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        )

    async def run_once(self) -> int:
        """One poll: claim/process batch and commit."""
        db = self.db_factory()
        try:
            disp = OutboxDispatcher(
                db,
                self.registry,
                max_dispatch_attempts=self.max_dispatch_attempts,
                record_dead_letter=self.record_dead_letter,
                worker_id=self.worker_id,
                lease_seconds=self.lease_seconds,
            )
            n = await disp.run_once(batch_limit=self.batch_limit)
            disp.update_operational_metrics()
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
