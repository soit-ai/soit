"""sync_worker

Knowledge connector sync worker: queues runs for sources whose schedule is due
and executes queued runs across tenants and workspaces.

It follows the ingest worker's shape. Runs are claimed through the shared lease
primitives, a heartbeat keeps the lease alive while a run executes, and a run
whose worker died is reclaimed once its lease expires; the engine re-lists the
remote and skips what the dead worker already finished, so a repeat is safe.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from collections.abc import Callable

from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.session import get_async_session_local
from app.kernel.commons.errors import ConflictError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.connectors import ConnectorRegistry
from app.kernel.runtime.common import lease
from app.modules.knowledge.application.connector_sync import (
    RUN_FAILED,
    KnowledgeSyncEngine,
    claim_next_run,
    enqueue_due_runs,
    fail_if_attempts_exhausted,
)
from app.modules.knowledge.domain.models import KnowledgeSource, KnowledgeSyncRun
from app.settings.settings import settings
from app.wiring.connectors import get_connector_registry
from app.wiring.container import get_container
from app.wiring.services import build_knowledge_runtime_service

logger = logging.getLogger(__name__)

SYSTEM_USER = "system"


def _default_session_factory() -> AsyncSession:
    return get_async_session_local()()


class GlobalKnowledgeSyncWorker:
    """Executes queued connector sync runs, and queues the scheduled ones."""

    def __init__(
        self,
        db_factory: Callable[[], AsyncSession] | None = None,
        *,
        worker_id: str | None = None,
        lease_seconds: int | None = None,
        scheduler_interval_seconds: float | None = None,
        registry: ConnectorRegistry | None = None,
    ) -> None:
        """Initialize the worker.

        Args:
            db_factory: Factory returning a database session.
            worker_id: Identifier recorded as the lease owner.
            lease_seconds: Lease duration held while a run executes.
            scheduler_interval_seconds: How often to look for due sources.
            registry: Connector kinds the worker can run.
        """
        self.db_factory = db_factory or _default_session_factory
        self.worker_id = worker_id or f"knowledge-sync-{uuid.uuid4()}"
        self.lease_seconds = lease.normalize_lease_seconds(
            lease_seconds if lease_seconds is not None else settings.knowledge_sync_worker_lease_seconds
        )
        self.scheduler_interval_seconds = max(
            1.0,
            float(
                scheduler_interval_seconds
                if scheduler_interval_seconds is not None
                else settings.knowledge_sync_scheduler_interval_seconds
            ),
        )
        self.registry = registry or get_connector_registry()
        self._last_scheduled = float("-inf")

    async def enqueue_due(self) -> int:
        """Queue runs for sources whose schedule fired; at most once per interval."""
        now = time.monotonic()
        if now - self._last_scheduled < self.scheduler_interval_seconds:
            return 0
        self._last_scheduled = now
        db = self.db_factory()
        try:
            return await enqueue_due_runs(db)
        except Exception:
            logger.warning("Knowledge sync scheduling failed", exc_info=True)
            return 0
        finally:
            await db.close()

    async def run_once(self) -> KnowledgeSyncRun | None:
        """Claim and execute one run across tenants."""
        db = self.db_factory()
        try:
            run = await claim_next_run(db, worker_id=self.worker_id, lease_seconds=self.lease_seconds)
            if run is None:
                return None
            if await fail_if_attempts_exhausted(db, run):
                logger.warning(
                    "Knowledge sync run abandoned after repeated interruptions",
                    extra={"run_id": run.id, "attempts": run.attempt_count},
                )
                return run

            source = await db.get(KnowledgeSource, run.source_id)
            user_id = run.requested_by or SYSTEM_USER
            ctx = RequestContext(
                tenant_id=run.tenant_id,
                workspace_id=run.workspace_id,
                user_id=user_id,
                tenant_role="Owner",
                workspace_role="Owner",
            )
            engine = KnowledgeSyncEngine(
                db=db,
                ctx=ctx,
                runtime=build_knowledge_runtime_service(db=db, ctx=ctx),
                registry=self.registry,
                secrets_port=get_container().get_secrets_port(ctx, db=db) if source and source.secret_id else None,
            )
            stop = asyncio.Event()
            lease_lost = asyncio.Event()
            heartbeat = asyncio.create_task(
                lease.LeaseHeartbeat(
                    self.db_factory,
                    KnowledgeSyncRun,
                    run.id,
                    worker_id=self.worker_id,
                    attempt_count=run.attempt_count,
                    lease_seconds=self.lease_seconds,
                    log_label="Knowledge sync lease",
                ).run(stop, lease_lost)
            )
            try:
                await engine.execute(run, lease_owner=self.worker_id)
            except ConflictError:
                # The lease was reclaimed mid-flight, so another worker owns the
                # run now. Its result stands; ours must not overwrite it.
                logger.warning(
                    "Knowledge sync lease was reclaimed; discarding this worker's outcome",
                    extra={"run_id": run.id},
                )
            except Exception as exc:
                logger.exception("Knowledge sync crashed", extra={"run_id": run.id})
                await self._fail_crashed(run.id, str(exc))
            finally:
                stop.set()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat
            return run
        finally:
            await db.close()

    async def _fail_crashed(self, run_id: str, message: str) -> None:
        """Record an unexpected crash on the run, if this worker still owns it."""
        db = self.db_factory()
        try:
            run = await db.get(KnowledgeSyncRun, run_id)
            if run is None or run.lease_owner != self.worker_id:
                return
            now = utc_now()
            run.status = RUN_FAILED
            run.error_code = "SYNC_ERROR"
            run.error_message = f"The sync stopped unexpectedly: {message}"[:1000]
            run.finished_at = now
            run.updated_at = now
            run.lease_owner = None
            run.lease_expires_at = None
            source = await db.get(KnowledgeSource, run.source_id)
            if source is not None:
                source.last_status = RUN_FAILED
                source.last_error = run.error_message
                source.last_sync_at = now
            await db.commit()
        except Exception:
            logger.warning("Could not record a crashed knowledge sync", extra={"run_id": run_id}, exc_info=True)
        finally:
            await db.close()

    async def run_loop(
        self,
        poll_interval: float = 5.0,
        max_runs: int | None = None,
        concurrency: int = 1,
        heartbeat_interval: float = 60.0,
    ) -> int:
        """Keep scheduling and executing runs until ``max_runs`` is reached (if set)."""
        processed = 0
        concurrency = max(1, int(concurrency or 1))
        heartbeat_interval = max(1.0, float(heartbeat_interval or 0))
        last_log = time.monotonic()
        while True:
            await self.enqueue_due()
            batch = [asyncio.create_task(self.run_once()) for _ in range(concurrency)]
            results = await asyncio.gather(*batch, return_exceptions=True)
            completed = 0
            for result in results:
                if isinstance(result, KnowledgeSyncRun):
                    completed += 1
                elif isinstance(result, Exception):
                    # Keep the worker alive even if one run fails unexpectedly.
                    logger.warning("Knowledge sync run failed: %s", result)
            if completed:
                processed += completed
                if max_runs is not None and processed >= max_runs:
                    break
                continue
            now = time.monotonic()
            if now - last_log >= heartbeat_interval:
                logger.info("Knowledge sync worker heartbeat: processed=%s concurrency=%s", processed, concurrency)
                last_log = now
            await asyncio.sleep(poll_interval)
        return processed
