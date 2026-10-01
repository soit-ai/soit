"""Knowledge source management: the operations behind the sources API.

A source ties an external system to a knowledge base. This service creates and
changes sources, tests connections, starts and cancels sync runs, and reads run
history. Executing a run is the sync engine's job, driven by the sync worker.

Authorization follows the knowledge base the source belongs to: reading needs
read access to it, and everything that changes or runs a source needs update
access. Every query is scoped to the caller's tenant and workspace.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from sqlalchemy import and_, desc, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import (
    ConflictError,
    KernelError,
    NotFoundError,
    ValidationError,
)
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.guard import rbac_guard
from app.kernel.identity.permissions import RESOURCE_KNOWLEDGE, ResourceVisibility
from app.kernel.ports.connectors import (
    ConnectionReport,
    ConnectorDescriptor,
    ConnectorError,
    ConnectorRegistration,
    ConnectorRegistry,
)
from app.kernel.ports.secrets.interface import SecretsPort, require_opaque_secret_id
from app.kernel.runtime.schedules.cron import (
    CronError,
    next_fire_after,
    resolve_timezone,
)
from app.modules.knowledge.application.connector_schemas import (
    SourceCreateRequest,
    SourceLimitsPayload,
    SourceTestRequest,
    SourceUpdateRequest,
)
from app.modules.knowledge.application.connector_sync import (
    ACTIVE_RUN_STATUSES,
    RUN_CANCELED,
    RUN_QUEUED,
    RUN_RUNNING,
    SyncLimits,
    compute_next_sync,
    create_sync_run,
    read_secret_value,
    record_source_audit,
)
from app.modules.knowledge.application.runtime_service import KnowledgeRuntimeService
from app.modules.knowledge.domain.models import KnowledgeSource, KnowledgeSyncRun
from app.modules.knowledge.domain.visibility import knowledge_visibility
from app.settings.settings import settings

MAX_SOURCES_PER_KNOWLEDGE = 20
TEST_TIMEOUT_SECONDS = 60.0
MAX_RUN_PAGE = 100
LIMIT_KEYS = ("max_items", "max_item_bytes", "max_total_bytes")


def _limit_ceilings() -> dict[str, int]:
    return {
        "max_items": settings.knowledge_sync_max_items_ceiling,
        "max_item_bytes": settings.knowledge_sync_max_item_bytes_ceiling,
        "max_total_bytes": settings.knowledge_sync_max_total_bytes_ceiling,
    }


def _config_error(exc: ConnectorError) -> ValidationError:
    """A connector's complaint about its configuration, as a validation error."""
    return ValidationError(exc.message, {"code": exc.code})


class KnowledgeSourceService:
    """Create, change, test, run and inspect knowledge sources."""

    def __init__(
        self,
        *,
        db: AsyncSession,
        ctx: RequestContext,
        runtime: KnowledgeRuntimeService,
        registry: ConnectorRegistry,
        secrets_port: SecretsPort | None,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.runtime = runtime
        self.registry = registry
        self.secrets_port = secrets_port

    async def _knowledge_visibility(self, knowledge_id: str) -> ResourceVisibility | None:
        return knowledge_visibility(await self.runtime.knowledge_repo.get_by_id(knowledge_id))

    # ------------------------------------------------------------ connectors

    def list_connectors(self) -> list[ConnectorDescriptor]:
        """The connector kinds this deployment offers."""
        return self.registry.descriptors()

    # --------------------------------------------------------------- sources

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id", visibility_resolver=_knowledge_visibility)
    async def list_sources(self, knowledge_id: str) -> list[tuple[KnowledgeSource, str | None]]:
        """Sources of a knowledge base with the id of each one's active run, if any."""
        await self.runtime.get_knowledge(knowledge_id)
        sources = list(
            (
                await self.db.exec(
                    select(KnowledgeSource)
                    .where(*self._scope(KnowledgeSource), KnowledgeSource.knowledge_id == knowledge_id)
                    .order_by(KnowledgeSource.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        active = await self._active_run_ids([source.id for source in sources])
        return [(source, active.get(source.id)) for source in sources]

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id", visibility_resolver=_knowledge_visibility)
    async def get_source(self, knowledge_id: str, source_id: str) -> tuple[KnowledgeSource, str | None]:
        source = await self._get_source(knowledge_id, source_id)
        active = await self._active_run_ids([source.id])
        return source, active.get(source.id)

    @rbac_guard(RESOURCE_KNOWLEDGE, "update", resource_id_arg="knowledge_id", visibility_resolver=_knowledge_visibility)
    async def create_source(self, knowledge_id: str, payload: SourceCreateRequest) -> KnowledgeSource:
        await self.runtime.get_knowledge(knowledge_id)
        registration = self._registration(payload.connector_kind)
        config = await self._validated_config(registration, payload.config)
        await self._validate_secret(registration, payload.secret_id)
        cron, timezone = self._validated_schedule(payload.schedule_cron, payload.schedule_timezone)
        limits = self._validated_limits(payload.limits)
        name = payload.name.strip()
        await self._require_free_name(knowledge_id, name)
        count = (
            await self.db.exec(
                select(func.count())
                .select_from(KnowledgeSource)
                .where(*self._scope(KnowledgeSource), KnowledgeSource.knowledge_id == knowledge_id)
            )
        ).scalar_one()
        if int(count or 0) >= MAX_SOURCES_PER_KNOWLEDGE:
            raise ValidationError(f"A knowledge base can have at most {MAX_SOURCES_PER_KNOWLEDGE} sources")

        now = utc_now()
        source = KnowledgeSource(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            knowledge_id=knowledge_id,
            name=name,
            connector_kind=payload.connector_kind,
            config_json=config,
            secret_id=payload.secret_id,
            limits_json=limits,
            schedule_cron=cron,
            schedule_timezone=timezone,
            enabled=payload.enabled,
            delete_removed=payload.delete_removed,
            created_by=self.ctx.user_id,
            updated_by=self.ctx.user_id,
        )
        source.next_sync_at = compute_next_sync(source, after=now)
        self.db.add(source)
        await self.db.flush()
        record_source_audit(
            self.db,
            self.ctx,
            event_type="knowledge.source.created",
            operation="create",
            source_id=source.id,
            payload={
                "knowledge_id": knowledge_id,
                "name": name,
                "connector_kind": source.connector_kind,
                "scheduled": bool(cron),
                "delete_removed": source.delete_removed,
            },
        )
        await self.db.commit()
        return source

    @rbac_guard(RESOURCE_KNOWLEDGE, "update", resource_id_arg="knowledge_id", visibility_resolver=_knowledge_visibility)
    async def update_source(
        self, knowledge_id: str, source_id: str, payload: SourceUpdateRequest
    ) -> KnowledgeSource:
        source = await self._get_source(knowledge_id, source_id)
        sent = payload.model_fields_set
        changed: list[str] = []
        registration = self._registration(source.connector_kind)

        if "name" in sent and payload.name is not None and payload.name.strip() != source.name:
            name = payload.name.strip()
            await self._require_free_name(knowledge_id, name, ignore=source.id)
            source.name = name
            changed.append("name")
        if "config" in sent and payload.config is not None:
            source.config_json = await self._validated_config(registration, payload.config)
            changed.append("config")
        if "secret_id" in sent and payload.secret_id != source.secret_id:
            await self._validate_secret(registration, payload.secret_id)
            source.secret_id = payload.secret_id
            changed.append("secret")
        elif "config" in sent and source.secret_id:
            # New settings are checked against the credentials already attached.
            await self._validate_secret(registration, source.secret_id)
        schedule_changed = False
        if "schedule_cron" in sent or "schedule_timezone" in sent:
            cron = payload.schedule_cron if "schedule_cron" in sent else source.schedule_cron
            timezone = payload.schedule_timezone if payload.schedule_timezone else source.schedule_timezone
            source.schedule_cron, source.schedule_timezone = self._validated_schedule(cron, timezone)
            schedule_changed = True
            changed.append("schedule")
        if "enabled" in sent and payload.enabled is not None and payload.enabled != source.enabled:
            source.enabled = payload.enabled
            schedule_changed = True
            changed.append("enabled")
        if "delete_removed" in sent and payload.delete_removed is not None:
            if payload.delete_removed != source.delete_removed:
                changed.append("delete_removed")
            source.delete_removed = payload.delete_removed
        if "limits" in sent:
            source.limits_json = self._merged_limits(source.limits_json, payload.limits)
            changed.append("limits")

        if schedule_changed:
            source.next_sync_at = compute_next_sync(source, after=utc_now())
        source.updated_by = self.ctx.user_id
        source.updated_at = utc_now()
        record_source_audit(
            self.db,
            self.ctx,
            event_type="knowledge.source.updated",
            operation="update",
            source_id=source.id,
            payload={"knowledge_id": knowledge_id, "changed": changed},
        )
        await self.db.commit()
        return source

    @rbac_guard(RESOURCE_KNOWLEDGE, "update", resource_id_arg="knowledge_id", visibility_resolver=_knowledge_visibility)
    async def delete_source(self, knowledge_id: str, source_id: str) -> None:
        """Delete a source. Documents it already synced stay in the knowledge base."""
        source = await self._get_source(knowledge_id, source_id)
        now = utc_now()
        runs = (
            await self.db.exec(
                select(KnowledgeSyncRun).where(
                    *self._scope(KnowledgeSyncRun),
                    KnowledgeSyncRun.source_id == source.id,
                    KnowledgeSyncRun.status.in_(ACTIVE_RUN_STATUSES),
                )
            )
        ).scalars().all()
        for run in runs:
            if run.status == RUN_QUEUED:
                run.status = RUN_CANCELED
                run.finished_at = now
                run.lease_owner = None
                run.lease_expires_at = None
            else:
                run.cancel_requested = True
            run.updated_at = now
        source.deleted_at = now
        source.enabled = False
        source.next_sync_at = None
        source.updated_by = self.ctx.user_id
        source.updated_at = now
        record_source_audit(
            self.db,
            self.ctx,
            event_type="knowledge.source.deleted",
            operation="delete",
            source_id=source.id,
            payload={"knowledge_id": knowledge_id, "name": source.name, "connector_kind": source.connector_kind},
        )
        await self.db.commit()

    # ----------------------------------------------------------------- tests

    @rbac_guard(RESOURCE_KNOWLEDGE, "update", resource_id_arg="knowledge_id", visibility_resolver=_knowledge_visibility)
    async def check_connection(self, knowledge_id: str, source_id: str) -> ConnectionReport:
        """Check a saved source's endpoint and credentials; nothing is ingested."""
        source = await self._get_source(knowledge_id, source_id)
        return await self._test(source.connector_kind, dict(source.config_json or {}), source.secret_id)

    @rbac_guard(RESOURCE_KNOWLEDGE, "update", resource_id_arg="knowledge_id", visibility_resolver=_knowledge_visibility)
    async def check_draft_connection(self, knowledge_id: str, payload: SourceTestRequest) -> ConnectionReport:
        """Check a connection that has not been saved."""
        await self.runtime.get_knowledge(knowledge_id)
        return await self._test(payload.connector_kind, dict(payload.config), payload.secret_id)

    async def _test(self, kind: str, config: dict[str, Any], secret_id: str | None) -> ConnectionReport:
        registration = self._registration(kind)
        try:
            normalized = registration.validate_config(config)
            secret_value = await self._read_secret(registration, secret_id)
            registration.validate_credentials(secret_value)
            connector = registration.factory(self.ctx, normalized, secret_value)
            return await asyncio.wait_for(connector.test_connection(sample_size=10), timeout=TEST_TIMEOUT_SECONDS)
        except ConnectorError as exc:
            return ConnectionReport(ok=False, message=exc.message)
        except TimeoutError:
            return ConnectionReport(ok=False, message="The connection test took too long and was stopped")

    # ------------------------------------------------------------------ runs

    @rbac_guard(RESOURCE_KNOWLEDGE, "update", resource_id_arg="knowledge_id", visibility_resolver=_knowledge_visibility)
    async def trigger_sync(self, knowledge_id: str, source_id: str) -> KnowledgeSyncRun:
        """Queue a sync of the source now; a sync already queued or running makes this a conflict."""
        source = await self._get_source(knowledge_id, source_id)
        if not source.enabled:
            raise ValidationError("This source is disabled; enable it before syncing")
        await self.runtime._require_index(knowledge_id)
        return await create_sync_run(self.db, source, trigger="manual", requested_by=self.ctx.user_id)

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id", visibility_resolver=_knowledge_visibility)
    async def list_runs(
        self, knowledge_id: str, source_id: str, *, limit: int = 20, offset: int = 0
    ) -> list[KnowledgeSyncRun]:
        source = await self._get_source(knowledge_id, source_id)
        rows = (
            await self.db.exec(
                select(KnowledgeSyncRun)
                .where(*self._scope(KnowledgeSyncRun), KnowledgeSyncRun.source_id == source.id)
                .order_by(desc(KnowledgeSyncRun.created_at))
                .offset(max(0, offset))
                .limit(max(1, min(limit, MAX_RUN_PAGE)))
            )
        ).scalars().all()
        return list(rows)

    @rbac_guard(RESOURCE_KNOWLEDGE, "read", resource_id_arg="knowledge_id", visibility_resolver=_knowledge_visibility)
    async def get_run(self, knowledge_id: str, source_id: str, run_id: str) -> KnowledgeSyncRun:
        source = await self._get_source(knowledge_id, source_id)
        return await self._get_run(source, run_id)

    @rbac_guard(RESOURCE_KNOWLEDGE, "update", resource_id_arg="knowledge_id", visibility_resolver=_knowledge_visibility)
    async def cancel_run(self, knowledge_id: str, source_id: str, run_id: str) -> KnowledgeSyncRun:
        """Cancel a queued run at once, or ask a running one to stop between items."""
        source = await self._get_source(knowledge_id, source_id)
        run = await self._get_run(source, run_id)
        now = utc_now()
        if run.status == RUN_QUEUED:
            run.status = RUN_CANCELED
            run.finished_at = now
            run.lease_owner = None
            run.lease_expires_at = None
            source.last_status = RUN_CANCELED
        elif run.status == RUN_RUNNING:
            run.cancel_requested = True
        else:
            raise ConflictError(f"The run already finished ({run.status})")
        run.updated_at = now
        await self.db.commit()
        return run

    # --------------------------------------------------------------- helpers

    def _scope(self, model: Any) -> list[Any]:
        """Tenant and workspace filters, plus "not deleted" for sources."""
        clauses = [model.tenant_id == self.ctx.tenant_id, model.workspace_id == self.ctx.workspace_id]
        if model is KnowledgeSource:
            clauses.append(model.deleted_at.is_(None))
        return clauses

    async def _get_source(self, knowledge_id: str, source_id: str) -> KnowledgeSource:
        source = (
            await self.db.exec(
                select(KnowledgeSource).where(
                    *self._scope(KnowledgeSource),
                    KnowledgeSource.id == source_id,
                    KnowledgeSource.knowledge_id == knowledge_id,
                )
            )
        ).scalars().first()
        if source is None:
            raise NotFoundError(f"Source {source_id} not found")
        return source

    async def _get_run(self, source: KnowledgeSource, run_id: str) -> KnowledgeSyncRun:
        run = (
            await self.db.exec(
                select(KnowledgeSyncRun).where(
                    *self._scope(KnowledgeSyncRun),
                    KnowledgeSyncRun.id == run_id,
                    KnowledgeSyncRun.source_id == source.id,
                )
            )
        ).scalars().first()
        if run is None:
            raise NotFoundError(f"Run {run_id} not found")
        return run

    async def _active_run_ids(self, source_ids: list[str]) -> dict[str, str]:
        if not source_ids:
            return {}
        rows = (
            await self.db.exec(
                select(KnowledgeSyncRun.source_id, KnowledgeSyncRun.id).where(
                    *self._scope(KnowledgeSyncRun),
                    KnowledgeSyncRun.source_id.in_(source_ids),
                    KnowledgeSyncRun.status.in_(ACTIVE_RUN_STATUSES),
                )
            )
        ).all()
        return {row[0]: row[1] for row in rows}

    async def _require_free_name(self, knowledge_id: str, name: str, *, ignore: str | None = None) -> None:
        clauses = [
            *self._scope(KnowledgeSource),
            KnowledgeSource.knowledge_id == knowledge_id,
            func.lower(KnowledgeSource.name) == name.lower(),
        ]
        if ignore:
            clauses.append(KnowledgeSource.id != ignore)
        existing = (await self.db.exec(select(KnowledgeSource.id).where(and_(*clauses)))).first()
        if existing is not None:
            raise ConflictError(f"A source named {name!r} already exists on this knowledge base")

    def _registration(self, kind: str) -> ConnectorRegistration:
        try:
            return self.registry.get(kind)
        except ConnectorError as exc:
            raise _config_error(exc) from exc

    async def _validated_config(
        self, registration: ConnectorRegistration, config: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            return registration.validate_config(config)
        except ConnectorError as exc:
            raise _config_error(exc) from exc

    async def _read_secret(self, registration: ConnectorRegistration, secret_id: str | None) -> str | None:
        """Resolve a secret the source points at, without ever repeating its value."""
        needs = registration.descriptor.secret
        if not secret_id:
            if needs == "required":
                raise ConnectorError(ConnectorError.CREDENTIALS_INVALID, "This connector needs a secret with credentials")
            return None
        if needs == "none":
            raise ConnectorError(ConnectorError.CREDENTIALS_INVALID, "This connector does not take a secret")
        try:
            secret_id = require_opaque_secret_id(secret_id)
        except KernelError as exc:
            raise ConnectorError(ConnectorError.CREDENTIALS_INVALID, "The secret id is not valid") from exc
        return await read_secret_value(self.secrets_port, secret_id)

    async def _validate_secret(self, registration: ConnectorRegistration, secret_id: str | None) -> None:
        """Check the secret exists and has the shape the connector expects."""
        try:
            value = await self._read_secret(registration, secret_id)
            registration.validate_credentials(value)
        except ConnectorError as exc:
            raise _config_error(exc) from exc

    @staticmethod
    def _validated_schedule(cron: str | None, timezone: str | None) -> tuple[str | None, str]:
        zone = (timezone or "UTC").strip() or "UTC"
        try:
            resolve_timezone(zone)
        except CronError as exc:
            raise ValidationError(str(exc)) from exc
        expression = (cron or "").strip()
        if not expression:
            return None, zone
        try:
            now = utc_now()
            first = next_fire_after(expression, now, timezone=zone)
            second = next_fire_after(expression, first, timezone=zone)
        except CronError as exc:
            raise ValidationError(f"Invalid schedule: {exc}") from exc
        minimum = max(60, int(settings.knowledge_sync_min_interval_seconds))
        if second - first < timedelta(seconds=minimum):
            raise ValidationError(f"Syncs may run at most once every {minimum // 60} minutes")
        return expression, zone

    @classmethod
    def _merged_limits(cls, current: dict[str, Any] | None, limits: SourceLimitsPayload | None) -> dict[str, Any]:
        """Apply a limits change to the stored caps.

        Only the caps named in the request change, so adjusting one does not
        reset the others; naming a cap as null returns it to the deployment
        default, and sending ``limits: null`` clears them all.
        """
        if limits is None:
            return {}
        merged = dict(current or {})
        for key in limits.model_fields_set:
            if getattr(limits, key) is None:
                merged.pop(key, None)
        merged.update(cls._validated_limits(limits))
        return merged

    @staticmethod
    def _validated_limits(limits: SourceLimitsPayload | None) -> dict[str, Any]:
        if limits is None:
            return {}
        ceilings = _limit_ceilings()
        result: dict[str, Any] = {}
        for key in LIMIT_KEYS:
            value = getattr(limits, key)
            if value is None:
                continue
            if value > ceilings[key]:
                raise ValidationError(f"{key} may be at most {ceilings[key]}")
            result[key] = int(value)
        return result

    @staticmethod
    def effective_limits(source: KnowledgeSource) -> SyncLimits:
        """The caps a run of ``source`` applies, defaults and ceilings included."""
        return SyncLimits.from_json(source.limits_json)
