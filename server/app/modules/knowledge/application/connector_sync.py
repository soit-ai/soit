"""Knowledge connector sync engine.

Runs one sync of a knowledge source: list what the remote holds, compare it with
what the previous sync recorded, and bring the knowledge base in step.

Per item the outcome is one of

* added      - new remote item, ingested as a new document;
* updated    - remote content changed, ingested as a new version of the same
               document key;
* unchanged  - nothing to do (matched on ETag / modification marker, or the
               downloaded bytes hash to what was ingested last time);
* removed    - the item is gone from the remote (and its document is deleted
               when the source asks for that);
* failed     - this item could not be synced; the rest of the run carries on.

Ingestion reuses the knowledge runtime's queued ingest path, so parsing,
chunking, embedding and their retries behave exactly as for an upload.

A listing or credential failure fails the whole run. Removal is decided only
from a complete listing: a run that hit a cap, was canceled or failed part way
never deletes anything.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import ConflictError, KernelError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.connectors import (
    ConnectorError,
    ConnectorItem,
    ConnectorRegistry,
    KnowledgeConnector,
    KnownItem,
)
from app.kernel.ports.secrets.interface import SecretsPort
from app.kernel.runtime.common import lease
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.schedules.cron import CronError, next_fire_after
from app.modules.knowledge.application.runtime_schemas import DocumentUpload
from app.modules.knowledge.application.runtime_service import KnowledgeRuntimeService
from app.modules.knowledge.domain.models import (
    Knowledge,
    KnowledgeDocument,
    KnowledgeSource,
    KnowledgeSourceItem,
    KnowledgeSyncRun,
)
from app.settings.settings import settings

logger = logging.getLogger(__name__)

RUN_QUEUED = "queued"
RUN_RUNNING = "running"
RUN_SUCCEEDED = "succeeded"
RUN_PARTIAL = "partial"
RUN_FAILED = "failed"
RUN_CANCELED = "canceled"
ACTIVE_RUN_STATUSES = (RUN_QUEUED, RUN_RUNNING)
TERMINAL_RUN_STATUSES = (RUN_SUCCEEDED, RUN_PARTIAL, RUN_FAILED, RUN_CANCELED)

ITEM_PRESENT = "present"
ITEM_REMOVED = "removed"
ITEM_FAILED = "failed"

SOURCE_KIND_CONNECTOR = "connector"
MAX_RECORDED_OUTCOMES = 200
MAX_EXTERNAL_ID_LENGTH = 1024
MAX_ERROR_LENGTH = 1000

AUDIT_RESOURCE_TYPE = "knowledge_source"


@dataclass(frozen=True)
class SyncLimits:
    """Per-run caps, always within the deployment's ceilings."""

    max_items: int
    max_item_bytes: int
    max_total_bytes: int

    @classmethod
    def from_json(cls, data: dict[str, Any] | None) -> SyncLimits:
        """Limits from a source's ``limits_json``, defaulting and clamping each."""
        data = data or {}

        def pick(key: str, default: int, ceiling: int) -> int:
            raw = data.get(key)
            try:
                value = int(raw) if raw is not None else int(default)
            except (TypeError, ValueError):
                value = int(default)
            return max(1, min(value, int(ceiling)))

        return cls(
            max_items=pick(
                "max_items",
                settings.knowledge_sync_default_max_items,
                settings.knowledge_sync_max_items_ceiling,
            ),
            max_item_bytes=pick(
                "max_item_bytes",
                settings.knowledge_sync_default_max_item_bytes,
                settings.knowledge_sync_max_item_bytes_ceiling,
            ),
            max_total_bytes=pick(
                "max_total_bytes",
                settings.knowledge_sync_default_max_total_bytes,
                settings.knowledge_sync_max_total_bytes_ceiling,
            ),
        )


def connector_doc_key(source_id: str, external_id: str) -> str:
    """The document key a source item's versions are stored under.

    Derived from the source and the remote identity, so the same item always
    lands on the same key however long or unusual its identity is.
    """
    digest = hashlib.sha256(external_id.encode("utf-8")).hexdigest()[:32]
    return f"{source_id}:{digest}"


def compute_next_sync(source: KnowledgeSource, *, after: datetime) -> datetime | None:
    """When the source's schedule next fires after ``after``, or None for manual-only."""
    if not source.schedule_cron or not source.enabled:
        return None
    try:
        return next_fire_after(source.schedule_cron, after, timezone=source.schedule_timezone)
    except CronError:
        # A stored expression that no longer parses must not wedge the scheduler.
        logger.warning("Knowledge source has an invalid schedule", extra={"source_id": source.id})
        return None


def record_source_audit(
    db: AsyncSession,
    ctx: RequestContext,
    *,
    event_type: str,
    operation: str,
    source_id: str | None,
    outcome: str = "allowed",
    payload: dict[str, Any] | None = None,
) -> None:
    """Stage an audit event for a source change or sync; the caller commits."""
    db.add(
        AuditEvent(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            event_type=event_type,
            resource_type=AUDIT_RESOURCE_TYPE,
            resource_id=source_id,
            operation=operation,
            actor_user_id=ctx.user_id,
            trace_id=ctx.trace_id,
            outcome=outcome,
            scope="workspace",
            payload_json=payload or {},
        )
    )


async def create_sync_run(
    db: AsyncSession,
    source: KnowledgeSource,
    *,
    trigger: str,
    requested_by: str | None,
) -> KnowledgeSyncRun:
    """Queue a run for ``source``; one active run per source is enforced by the store."""
    run = KnowledgeSyncRun(
        tenant_id=source.tenant_id,
        workspace_id=source.workspace_id,
        knowledge_id=source.knowledge_id,
        source_id=source.id,
        trigger=trigger,
        status=RUN_QUEUED,
        requested_by=requested_by,
    )
    try:
        # A savepoint, so losing the race to another queued run undoes only
        # this insert and leaves the caller's session usable.
        async with db.begin_nested():
            db.add(run)
            await db.flush()
    except IntegrityError as exc:
        raise ConflictError("A sync is already queued or running for this source") from exc
    source.last_status = RUN_QUEUED
    source.updated_at = utc_now()
    await db.commit()
    return run


async def enqueue_due_runs(db: AsyncSession, *, now: datetime | None = None, limit: int = 50) -> int:
    """Queue a run for every enabled source whose schedule is due.

    Works across tenants, as the workers do. Each source row is locked while
    its schedule advances, so replicas polling at once do not queue it twice;
    the store's one-active-run rule is the backstop.
    """
    moment = now or utc_now()
    queued = 0
    candidates = (
        await db.exec(
            select(KnowledgeSource.id)
            .join(
                Knowledge,
                and_(
                    Knowledge.id == KnowledgeSource.knowledge_id,
                    Knowledge.tenant_id == KnowledgeSource.tenant_id,
                    Knowledge.workspace_id == KnowledgeSource.workspace_id,
                ),
            )
            .where(
                KnowledgeSource.enabled.is_(True),
                KnowledgeSource.deleted_at.is_(None),
                KnowledgeSource.schedule_cron.is_not(None),
                KnowledgeSource.next_sync_at.is_not(None),
                KnowledgeSource.next_sync_at <= moment,
                Knowledge.deleted_at.is_(None),
                Knowledge.status == "active",
            )
            .order_by(KnowledgeSource.next_sync_at.asc())
            .limit(limit)
        )
    ).scalars().all()

    for source_id in candidates:
        source = (
            await db.exec(
                select(KnowledgeSource)
                .where(
                    KnowledgeSource.id == source_id,
                    KnowledgeSource.next_sync_at <= moment,
                    KnowledgeSource.deleted_at.is_(None),
                )
                .with_for_update(skip_locked=True)
            )
        ).scalars().first()
        if source is None:
            continue
        source.next_sync_at = compute_next_sync(source, after=moment)
        try:
            await create_sync_run(db, source, trigger="schedule", requested_by=None)
            queued += 1
        except ConflictError:
            # A run is still going; the schedule has already moved on, so this
            # firing is skipped rather than stacked behind it.
            await db.commit()
    return queued


class _Counters:
    """Per-outcome counts for one run."""

    def __init__(self) -> None:
        self.added = 0
        self.updated = 0
        self.unchanged = 0
        self.removed = 0
        self.failed = 0
        self.skipped = 0

    def as_json(self) -> dict[str, int]:
        return {
            "added": self.added,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "removed": self.removed,
            "failed": self.failed,
            "skipped": self.skipped,
        }


class _RunStopped(Exception):
    """The run was canceled while it executed."""


class KnowledgeSyncEngine:
    """Executes one claimed sync run."""

    def __init__(
        self,
        *,
        db: AsyncSession,
        ctx: RequestContext,
        runtime: KnowledgeRuntimeService,
        registry: ConnectorRegistry,
        secrets_port: SecretsPort | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.runtime = runtime
        self.registry = registry
        self.secrets_port = secrets_port
        self.clock = clock
        self._lease_owner: str | None = None

    # ------------------------------------------------------------------ entry

    async def execute(self, run: KnowledgeSyncRun, *, lease_owner: str | None = None) -> KnowledgeSyncRun:
        """Run the sync, record its outcome, and return the finished run.

        ``lease_owner`` makes every write conditional on the worker still
        holding the run, so one that was superseded cannot overwrite the
        outcome of the worker that took over.
        """
        self._lease_owner = lease_owner
        run.started_at = run.started_at or self.clock()
        run.added_count = run.updated_count = run.unchanged_count = 0
        run.removed_count = run.failed_count = run.skipped_count = 0
        run.truncated = False
        run.outcomes_json = []
        run.error_code = None
        run.error_message = None
        await self.db.commit()

        source = await self._load_source(run)
        if source is None:
            return await self._finish(run, None, RUN_FAILED, "NOT_FOUND", "The source no longer exists")
        knowledge = await self.runtime.knowledge_repo.get_by_id(source.knowledge_id)
        if knowledge is None:
            return await self._finish(run, source, RUN_FAILED, "NOT_FOUND", "The knowledge base no longer exists")

        record_source_audit(
            self.db,
            self.ctx,
            event_type="knowledge.source.sync.started",
            operation="sync",
            source_id=source.id,
            outcome="started",
            payload={"run_id": run.id, "trigger": run.trigger, "connector_kind": source.connector_kind},
        )
        await self.db.commit()

        counters = _Counters()
        try:
            await self.runtime._require_index(knowledge.id)
            connector = await self._build_connector(source)
            truncated = await self._sync(run, source, knowledge, connector, counters)
        except _RunStopped:
            return await self._finish(run, source, RUN_CANCELED, None, None, counters=counters)
        except ConnectorError as exc:
            return await self._finish(run, source, RUN_FAILED, exc.code, exc.message, counters=counters)
        except ConflictError:
            raise
        except SQLAlchemyError:
            raise
        except KernelError as exc:
            return await self._finish(run, source, RUN_FAILED, exc.code, exc.message, counters=counters)
        except Exception as exc:
            logger.exception("Knowledge sync failed", extra={"run_id": run.id})
            return await self._finish(run, source, RUN_FAILED, "SYNC_ERROR", str(exc), counters=counters)

        status = RUN_PARTIAL if counters.failed else RUN_SUCCEEDED
        return await self._finish(run, source, status, None, None, counters=counters, truncated=truncated)

    # --------------------------------------------------------------- the sync

    async def _sync(
        self,
        run: KnowledgeSyncRun,
        source: KnowledgeSource,
        knowledge: Knowledge,
        connector: KnowledgeConnector,
        counters: _Counters,
    ) -> bool:
        """Sync every listed item; returns whether a cap ended the listing early."""
        limits = SyncLimits.from_json(source.limits_json)
        items = await self._load_items(source.id)
        live_documents = await self._live_document_ids(
            {item.document_id for item in items.values() if item.document_id}
        )
        known = {
            external_id: KnownItem(
                etag=item.remote_etag,
                modified=item.remote_modified,
                meta=dict(item.meta_json or {}),
            )
            for external_id, item in items.items()
            if item.status == ITEM_PRESENT
        }

        seen: set[str] = set()
        total_bytes = 0
        listed = 0
        truncated = False

        async for entry in connector.iter_items(known):
            await self._checkpoint(run)
            if listed >= limits.max_items:
                truncated = True
                break
            listed += 1
            if len(entry.external_id) > MAX_EXTERNAL_ID_LENGTH:
                self._record(run, counters, "failed", entry, error="The item identifier is too long")
                continue
            seen.add(entry.external_id)
            existing = items.get(entry.external_id)
            try:
                outcome, downloaded = await self._sync_item(
                    run,
                    source,
                    knowledge,
                    connector,
                    entry,
                    existing,
                    items,
                    live_documents,
                    limits,
                    remaining_bytes=limits.max_total_bytes - total_bytes,
                )
            except (SQLAlchemyError, asyncio.CancelledError):
                raise
            except KernelError as exc:
                await self._fail_item(run, counters, source, entry, existing, items, exc.message)
                continue
            except Exception as exc:
                logger.warning("Knowledge sync item failed", extra={"run_id": run.id}, exc_info=True)
                await self._fail_item(run, counters, source, entry, existing, items, str(exc))
                continue

            total_bytes += downloaded
            if outcome == "budget":
                truncated = True
                break
            self._record(run, counters, outcome, entry)
            await self.db.commit()
            if total_bytes >= limits.max_total_bytes:
                truncated = True
                break

        stats = connector.stats()
        counters.skipped += int(stats.get("skipped", 0))
        if stats.get("incomplete"):
            # The connector stopped before it had seen everything (a crawl hit
            # its page cap), so what it did not report proves nothing.
            truncated = True

        complete = not truncated
        if complete:
            await self._handle_removed(run, source, knowledge, items, seen, live_documents, counters)
        run.truncated = truncated
        return truncated

    async def _sync_item(
        self,
        run: KnowledgeSyncRun,
        source: KnowledgeSource,
        knowledge: Knowledge,
        connector: KnowledgeConnector,
        entry: ConnectorItem,
        existing: KnowledgeSourceItem | None,
        items: dict[str, KnowledgeSourceItem],
        live_documents: set[str],
        limits: SyncLimits,
        *,
        remaining_bytes: int,
    ) -> tuple[str, int]:
        """Sync one item, returning its outcome and how many bytes it downloaded."""
        now = self.clock()
        if entry.error:
            raise ConnectorError(ConnectorError.ITEM_FAILED, entry.error)

        document_live = bool(existing and existing.document_id and existing.document_id in live_documents)
        if existing is not None and document_live and existing.status != ITEM_FAILED:
            if self._unchanged_by_metadata(entry, existing):
                existing.status = ITEM_PRESENT
                existing.last_seen_at = now
                existing.last_error = None
                existing.meta_json = dict(entry.meta or existing.meta_json or {})
                existing.updated_at = now
                return "unchanged", 0

        if entry.size is not None and entry.size > limits.max_item_bytes:
            raise ConnectorError(
                ConnectorError.ITEM_TOO_LARGE,
                f"The item is {entry.size} bytes, over the {limits.max_item_bytes} byte limit",
            )
        if entry.size is not None and entry.size > remaining_bytes:
            return "budget", 0

        fetched = await connector.fetch_item(entry, max_bytes=limits.max_item_bytes)
        content = fetched.content
        if len(content) > limits.max_item_bytes:
            raise ConnectorError(
                ConnectorError.ITEM_TOO_LARGE,
                f"The item is over the {limits.max_item_bytes} byte limit",
            )
        if not content:
            raise ConnectorError(ConnectorError.ITEM_FAILED, "The item is empty")
        content_hash = hashlib.sha256(content).hexdigest()

        etag = fetched.etag or entry.etag
        modified = fetched.modified or entry.modified
        size = len(content)

        if existing is not None and document_live and existing.content_hash == content_hash:
            existing.status = ITEM_PRESENT
            existing.remote_etag = etag
            existing.remote_modified = modified
            existing.remote_size = entry.size if entry.size is not None else size
            existing.meta_json = dict(entry.meta or {})
            existing.last_seen_at = now
            existing.last_error = None
            existing.updated_at = now
            return "unchanged", size

        doc_key = (existing.doc_key if existing is not None and existing.doc_key else None) or connector_doc_key(
            source.id, entry.external_id
        )
        had_document = document_live
        upload = DocumentUpload(
            doc_key=doc_key,
            source_kind=SOURCE_KIND_CONNECTOR,
            source_uri=entry.source_uri,
            external_id=entry.external_id,
            filename=fetched.filename or entry.name,
            mime_type=fetched.content_type,
            title=fetched.title or entry.name,
            size_bytes=size,
            checksum=content_hash,
            content_hash=content_hash,
        )
        document, _task = await self.runtime.enqueue_ingest_task(
            knowledge.id,
            upload,
            file_content=content,
        )

        if existing is None:
            existing = KnowledgeSourceItem(
                tenant_id=source.tenant_id,
                workspace_id=source.workspace_id,
                source_id=source.id,
                external_id=entry.external_id,
            )
            items[entry.external_id] = existing
        existing.doc_key = doc_key
        existing.document_id = document.id
        existing.remote_etag = etag
        existing.remote_modified = modified
        existing.remote_size = entry.size if entry.size is not None else size
        existing.content_hash = content_hash
        existing.status = ITEM_PRESENT
        existing.meta_json = dict(entry.meta or {})
        existing.last_seen_at = now
        existing.last_synced_at = now
        existing.last_error = None
        existing.updated_at = now
        self.db.add(existing)
        live_documents.add(document.id)
        return ("updated" if had_document else "added"), size

    @staticmethod
    def _unchanged_by_metadata(entry: ConnectorItem, existing: KnowledgeSourceItem) -> bool:
        """Whether the remote's own markers say the item is as it was."""
        if entry.size is not None and existing.remote_size is not None and entry.size != existing.remote_size:
            return False
        if entry.etag:
            return entry.etag == existing.remote_etag
        if entry.modified:
            return entry.modified == existing.remote_modified
        return False

    async def _fail_item(
        self,
        run: KnowledgeSyncRun,
        counters: _Counters,
        source: KnowledgeSource,
        entry: ConnectorItem,
        existing: KnowledgeSourceItem | None,
        items: dict[str, KnowledgeSourceItem],
        message: str,
    ) -> None:
        """Record one item's failure; the run carries on with the next."""
        await self._mark_item_failed(source, entry, existing, items, message)
        self._record(run, counters, "failed", entry, error=message)
        await self.db.commit()

    async def _mark_item_failed(
        self,
        source: KnowledgeSource,
        entry: ConnectorItem,
        existing: KnowledgeSourceItem | None,
        items: dict[str, KnowledgeSourceItem],
        message: str,
    ) -> None:
        now = self.clock()
        if existing is None:
            existing = KnowledgeSourceItem(
                tenant_id=source.tenant_id,
                workspace_id=source.workspace_id,
                source_id=source.id,
                external_id=entry.external_id,
            )
            items[entry.external_id] = existing
        existing.status = ITEM_FAILED
        existing.last_seen_at = now
        existing.last_error = message[:MAX_ERROR_LENGTH]
        existing.updated_at = now
        self.db.add(existing)
        await self.db.commit()

    async def _handle_removed(
        self,
        run: KnowledgeSyncRun,
        source: KnowledgeSource,
        knowledge: Knowledge,
        items: dict[str, KnowledgeSourceItem],
        seen: set[str],
        live_documents: set[str],
        counters: _Counters,
    ) -> None:
        """Retire items the complete listing no longer contains."""
        now = self.clock()
        for external_id, item in list(items.items()):
            if external_id in seen or item.status == ITEM_REMOVED:
                continue
            await self._checkpoint(run)
            entry = ConnectorItem(external_id=external_id, name=external_id)
            try:
                if source.delete_removed and item.doc_key:
                    await self._delete_item_documents(knowledge.id, item.doc_key)
                    if item.document_id:
                        live_documents.discard(item.document_id)
                    item.document_id = None
                item.status = ITEM_REMOVED
                item.last_error = None
                item.updated_at = now
                self.db.add(item)
                await self.db.commit()
            except SQLAlchemyError:
                raise
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Knowledge sync removal failed", extra={"run_id": run.id}, exc_info=True)
                self._record(run, counters, "failed", entry, error=f"Removal failed: {exc}")
                continue
            self._record(
                run,
                counters,
                "removed",
                entry,
                detail="document deleted" if source.delete_removed else "document kept",
            )
            await self.db.commit()

    async def _delete_item_documents(self, knowledge_id: str, doc_key: str) -> None:
        """Delete every live version stored under ``doc_key``."""
        versions = await self.runtime.versioning.list_versions(knowledge_id, doc_key)
        for version in versions:
            await self.runtime.delete_document(version.id)

    # ----------------------------------------------------------------- helpers

    async def _build_connector(self, source: KnowledgeSource) -> KnowledgeConnector:
        registration = self.registry.get(source.connector_kind)
        secret_value: str | None = None
        needs = registration.descriptor.secret
        if source.secret_id:
            if self.secrets_port is None:
                raise ConnectorError(ConnectorError.CREDENTIALS_INVALID, "Secrets are not available to the worker")
            try:
                secret_value = await self.secrets_port.get_secret(source.secret_id)
            except KernelError as exc:
                raise ConnectorError(
                    ConnectorError.CREDENTIALS_INVALID,
                    f"The source's secret could not be read ({exc.code})",
                ) from exc
        elif needs == "required":
            raise ConnectorError(ConnectorError.CREDENTIALS_INVALID, "This connector needs a secret")
        registration.validate_credentials(secret_value)
        return registration.factory(self.ctx, dict(source.config_json or {}), secret_value)

    async def _load_source(self, run: KnowledgeSyncRun) -> KnowledgeSource | None:
        return (
            await self.db.exec(
                select(KnowledgeSource).where(
                    KnowledgeSource.id == run.source_id,
                    KnowledgeSource.tenant_id == self.ctx.tenant_id,
                    KnowledgeSource.workspace_id == self.ctx.workspace_id,
                    KnowledgeSource.deleted_at.is_(None),
                )
            )
        ).scalars().first()

    async def _load_items(self, source_id: str) -> dict[str, KnowledgeSourceItem]:
        rows = (
            await self.db.exec(
                select(KnowledgeSourceItem).where(
                    KnowledgeSourceItem.source_id == source_id,
                    KnowledgeSourceItem.tenant_id == self.ctx.tenant_id,
                    KnowledgeSourceItem.workspace_id == self.ctx.workspace_id,
                )
            )
        ).scalars().all()
        return {row.external_id: row for row in rows}

    async def _live_document_ids(self, ids: set[str]) -> set[str]:
        """Which of the given documents still exist (a user may have deleted one)."""
        live: set[str] = set()
        pending = list(ids)
        for start in range(0, len(pending), 500):
            batch = pending[start : start + 500]
            rows = (
                await self.db.exec(
                    select(KnowledgeDocument.id).where(
                        KnowledgeDocument.tenant_id == self.ctx.tenant_id,
                        KnowledgeDocument.workspace_id == self.ctx.workspace_id,
                        KnowledgeDocument.id.in_(batch),
                        KnowledgeDocument.deleted_at.is_(None),
                    )
                )
            ).scalars().all()
            live.update(rows)
        return live

    async def _checkpoint(self, run: KnowledgeSyncRun) -> None:
        """Stop if the lease moved on or a cancel was requested."""
        await self.db.refresh(run)
        if self._lease_owner is not None and run.lease_owner != self._lease_owner:
            raise ConflictError(f"Sync run {run.id} is no longer owned by {self._lease_owner}")
        if run.cancel_requested:
            raise _RunStopped

    def _record(
        self,
        run: KnowledgeSyncRun,
        counters: _Counters,
        outcome: str,
        entry: ConnectorItem,
        *,
        error: str | None = None,
        detail: str | None = None,
    ) -> None:
        setattr(counters, outcome, getattr(counters, outcome) + 1)
        run.added_count = counters.added
        run.updated_count = counters.updated
        run.unchanged_count = counters.unchanged
        run.removed_count = counters.removed
        run.failed_count = counters.failed
        run.updated_at = self.clock()
        if outcome == "unchanged":
            return
        outcomes = list(run.outcomes_json or [])
        if len(outcomes) < MAX_RECORDED_OUTCOMES:
            record: dict[str, Any] = {
                "external_id": entry.external_id,
                "name": entry.name,
                "outcome": outcome,
            }
            if error:
                record["error"] = error[:MAX_ERROR_LENGTH]
            if detail:
                record["detail"] = detail
            outcomes.append(record)
            run.outcomes_json = outcomes

    async def _finish(
        self,
        run: KnowledgeSyncRun,
        source: KnowledgeSource | None,
        status: str,
        error_code: str | None,
        error_message: str | None,
        *,
        counters: _Counters | None = None,
        truncated: bool | None = None,
    ) -> KnowledgeSyncRun:
        now = self.clock()
        if self._lease_owner is not None:
            await self.db.refresh(run)
            if run.lease_owner != self._lease_owner:
                raise ConflictError(f"Sync run {run.id} is no longer owned by {self._lease_owner}")
        if counters is not None:
            run.added_count = counters.added
            run.updated_count = counters.updated
            run.unchanged_count = counters.unchanged
            run.removed_count = counters.removed
            run.failed_count = counters.failed
            run.skipped_count = counters.skipped
        if truncated is not None:
            run.truncated = truncated
        run.status = status
        run.error_code = error_code
        run.error_message = (error_message or "")[:MAX_ERROR_LENGTH] or None
        run.finished_at = now
        run.updated_at = now
        run.lease_owner = None
        run.lease_expires_at = None

        if source is not None:
            source.last_sync_at = now
            source.last_status = status
            source.last_error = run.error_message
            source.last_counts_json = {
                "added": run.added_count,
                "updated": run.updated_count,
                "unchanged": run.unchanged_count,
                "removed": run.removed_count,
                "failed": run.failed_count,
                "skipped": run.skipped_count,
                "truncated": bool(run.truncated),
            }
            source.updated_at = now
            record_source_audit(
                self.db,
                self.ctx,
                event_type="knowledge.source.sync.finished",
                operation="sync",
                source_id=source.id,
                outcome=status,
                payload={
                    "run_id": run.id,
                    "trigger": run.trigger,
                    "counts": source.last_counts_json,
                    "error_code": error_code,
                },
            )
        await self.db.commit()
        return run



async def fail_if_attempts_exhausted(db: AsyncSession, run: KnowledgeSyncRun) -> bool:
    """Fail a claimed run that has been claimed too many times; True when it did."""
    if int(run.attempt_count or 0) <= max(1, int(settings.knowledge_sync_max_attempts)):
        return False
    now = utc_now()
    run.status = RUN_FAILED
    run.error_code = "SYNC_ATTEMPTS_EXHAUSTED"
    run.error_message = "The sync was interrupted too many times and was given up"
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
    return True


async def claim_next_run(
    db: AsyncSession,
    *,
    worker_id: str,
    lease_seconds: int,
) -> KnowledgeSyncRun | None:
    """Claim a queued run, or reclaim one whose worker stopped renewing."""
    run = await lease.claim_next(
        db,
        KnowledgeSyncRun,
        worker_id=worker_id,
        lease_seconds=lease.normalize_lease_seconds(lease_seconds),
    )
    if run is None:
        return None
    if run.started_at is None:
        run.started_at = utc_now()
    await db.commit()
    return run


__all__ = [
    "ACTIVE_RUN_STATUSES",
    "KnowledgeSyncEngine",
    "RUN_CANCELED",
    "RUN_FAILED",
    "RUN_PARTIAL",
    "RUN_QUEUED",
    "RUN_RUNNING",
    "RUN_SUCCEEDED",
    "SyncLimits",
    "TERMINAL_RUN_STATUSES",
    "claim_next_run",
    "compute_next_sync",
    "connector_doc_key",
    "create_sync_run",
    "enqueue_due_runs",
    "fail_if_attempts_exhausted",
    "record_source_audit",
]
