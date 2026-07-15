"""ingest_worker

Knowledge ingestion task worker backed by knowledge persistence/runtime internals.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infra.db.session import get_db_sync
from app.kernel.commons.errors import KernelError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.modules.knowledge.application.service import KnowledgeService
from app.modules.knowledge.domain.models import KnowledgeIngestTask
from app.wiring.services import build_knowledge_service


class KnowledgeIngestWorker:
    """Worker that processes knowledge ingestion tasks."""

    def __init__(self, service: KnowledgeService):
        """Initialize ingest worker.

        Args:
            service: Knowledge service instance.
        """
        if not service.ingest_task_repo:
            raise KernelError("INGEST_TASK_REPO_NOT_AVAILABLE", "Ingest task repository is not configured")
        self.service = service

    async def run_once(self) -> KnowledgeIngestTask | None:
        """Claim and process one task."""
        task = self.service.ingest_task_repo.claim_next()
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
        logger = logging.getLogger(__name__)
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
    ):
        """Initialize global worker.

        Args:
            db_factory: Factory returning a database session.
        """
        self.db_factory = db_factory

    def _claim_next_task(self, db: Session) -> KnowledgeIngestTask | None:
        """Claim the next queued task without tenant/workspace scoping."""
        query = select(KnowledgeIngestTask).where(
            KnowledgeIngestTask.status == "queued"
        ).order_by(KnowledgeIngestTask.created_at.asc()).limit(1)
        try:
            query = query.with_for_update(skip_locked=True)
        except Exception:
            pass
        result = db.exec(query).first()
        if result is None:
            return None
        task = result if isinstance(result, KnowledgeIngestTask) else result[0]
        now = utc_now()
        task.status = "running"
        task.started_at = now
        task.updated_at = now
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
            await service.process_ingest_task(task)
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
        logger = logging.getLogger(__name__)
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
