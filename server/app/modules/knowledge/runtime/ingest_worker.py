"""ingest_worker

Knowledge ingestion task worker backed by knowledge persistence/runtime internals.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.infra.db.session import get_db_sync
from app.kernel.commons.errors import KernelError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.common import lease
from app.modules.knowledge.application.service import KnowledgeService
from app.modules.knowledge.domain.models import KnowledgeIngestTask
from app.settings.settings import settings
from app.wiring.services import build_knowledge_service

logger = logging.getLogger(__name__)


class KnowledgeIngestWorker:
    """Worker that processes knowledge ingestion tasks."""

    def __init__(self, service: KnowledgeService, *, worker_id: str | None = None):
        """Initialize ingest worker.

        Args:
            service: Knowledge service instance.
            worker_id: Identifier recorded as the lease owner.
        """
        if not service.ingest_task_repo:
            raise KernelError("INGEST_TASK_REPO_NOT_AVAILABLE", "Ingest task repository is not configured")
        self.service = service
        self.worker_id = worker_id or f"knowledge-ingest-{uuid.uuid4()}"
        self.lease_seconds = lease.normalize_lease_seconds(
            getattr(settings, "knowledge_ingest_worker_lease_seconds", None)
        )

    async def run_once(self) -> KnowledgeIngestTask | None:
        """Claim and process one task."""
        task = self.service.ingest_task_repo.claim_next(
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        if not task:
            return None
        try:
            await self.service.process_ingest_task(task)
        except Exception:
            return task
        return task

    async def run_loop(
        self,
        poll_interval: float = 1.0,
        max_tasks: int | None = None,
        concurrency: int = 1,
        heartbeat_interval: float = 30.0,
    ) -> int:
        """Continuously process tasks until max_tasks is reached (if set)."""
        processed = 0
        concurrency = max(1, int(concurrency or 1))
        heartbeat_interval = max(1.0, float(heartbeat_interval or 0))
        last_log = time.monotonic()
        last_completed_at: str | None = None
        while True:
            batch = [asyncio.create_task(self.run_once()) for _ in range(concurrency)]
            results = await asyncio.gather(*batch, return_exceptions=True)
            completed = 0
            for result in results:
                if isinstance(result, KnowledgeIngestTask):
                    completed += 1
                elif isinstance(result, Exception):
                    # Keep worker alive even if one task fails unexpectedly.
                    logger.warning("Ingest task failed: %s", result)
            if completed:
                processed += completed
                last_completed_at = str(utc_now())
                if max_tasks is not None and processed >= max_tasks:
                    break
                continue
            now = time.monotonic()
            if now - last_log >= heartbeat_interval:
                logger.info(
                    "Ingest worker heartbeat: processed=%s concurrency=%s last_completed_at=%s",
                    processed,
                    concurrency,
                    last_completed_at,
                )
                last_log = now
            await asyncio.sleep(poll_interval)
        return processed


class GlobalKnowledgeIngestWorker:
    """Worker that processes queued ingestion tasks across tenants/workspaces."""

    def __init__(
        self,
        db_factory: Callable[[], Session] = get_db_sync,
        *,
        worker_id: str | None = None,
        lease_seconds: int | None = None,
    ):
        """Initialize global worker.

        Args:
            db_factory: Factory returning a database session.
            worker_id: Identifier recorded as the lease owner.
            lease_seconds: Lease duration held while a task executes.
        """
        self.db_factory = db_factory
        self.worker_id = worker_id or f"knowledge-ingest-{uuid.uuid4()}"
        self.lease_seconds = lease.normalize_lease_seconds(
            lease_seconds
            if lease_seconds is not None
            else getattr(settings, "knowledge_ingest_worker_lease_seconds", None)
        )

    def _claim_next_task(self, db: Session) -> KnowledgeIngestTask | None:
        """Claim a queued task, or reclaim one whose worker stopped renewing."""
        task = lease.claim_next(
            db,
            KnowledgeIngestTask,
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        if task is None:
            return None
        if task.started_at is None:
            task.started_at = utc_now()
        task.updated_by = task.created_by or "system"
        db.commit()
        db.refresh(task)
        return task

    async def run_once(self) -> KnowledgeIngestTask | None:
        """Claim and process one task across tenants."""
        db = self.db_factory()
        try:
            task = self._claim_next_task(db)
            if not task:
                return None
            ctx = RequestContext(
                tenant_id=task.tenant_id,
                workspace_id=task.workspace_id,
                user_id=task.created_by or "system",
                tenant_role="Owner",
                workspace_role="Owner",
            )
            service = build_knowledge_service(db=db, ctx=ctx)
            stop = asyncio.Event()
            lease_lost = asyncio.Event()
            heartbeat = asyncio.create_task(
                lease.LeaseHeartbeat(
                    self.db_factory,
                    KnowledgeIngestTask,
                    task.id,
                    worker_id=self.worker_id,
                    attempt_count=task.attempt_count,
                    lease_seconds=self.lease_seconds,
                    log_label="Knowledge ingest lease",
                ).run(stop, lease_lost)
            )
            try:
                await service.process_ingest_task(task)
            finally:
                stop.set()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat
                if lease_lost.is_set():
                    logger.error(
                        "Knowledge ingest lease was lost while processing; "
                        "another worker may have reclaimed this task",
                        extra={"task_id": task.id},
                    )
            return task
        finally:
            db.close()

    async def run_loop(
        self,
        poll_interval: float = 1.0,
        max_tasks: int | None = None,
        concurrency: int = 1,
        heartbeat_interval: float = 30.0,
    ) -> int:
        """Continuously process tasks until max_tasks is reached (if set)."""
        processed = 0
        concurrency = max(1, int(concurrency or 1))
        heartbeat_interval = max(1.0, float(heartbeat_interval or 0))
        last_log = time.monotonic()
        last_completed_at: str | None = None
        while True:
            batch = [asyncio.create_task(self.run_once()) for _ in range(concurrency)]
            results = await asyncio.gather(*batch, return_exceptions=True)
            completed = 0
            for result in results:
                if isinstance(result, KnowledgeIngestTask):
                    completed += 1
                elif isinstance(result, Exception):
                    logger.warning("Ingest task failed: %s", result)
            if completed:
                processed += completed
                last_completed_at = str(utc_now())
                if max_tasks is not None and processed >= max_tasks:
                    break
                continue
            now = time.monotonic()
            if now - last_log >= heartbeat_interval:
                logger.info(
                    "Ingest worker heartbeat: processed=%s concurrency=%s last_completed_at=%s",
                    processed,
                    concurrency,
                    last_completed_at,
                )
                last_log = now
            await asyncio.sleep(poll_interval)
        return processed
