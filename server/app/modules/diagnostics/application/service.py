"""Build owner-visible diagnostics from live process and dependency state."""

from datetime import timedelta
from importlib.metadata import PackageNotFoundError, version
from time import perf_counter, time

import psutil
from sqlalchemy import func, text
from sqlmodel import Session, select

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.db.models.threads import Thread
from app.modules.agent.domain.models import Agent
from app.modules.diagnostics.application.schemas import (
    DependencyDiagnostic,
    DiagnosticsSnapshot,
    ProcessDiagnostic,
    WorkspaceDiagnostic,
)
from app.modules.feedback.domain.models import ProductFeedback
from app.modules.knowledge.domain.models import Knowledge
from app.modules.modelhub.domain.models import ProviderModel
from app.modules.plugin.domain.models import Plugin
from app.modules.workflow.domain.models import Workflow
from app.settings.settings import settings


class DiagnosticsService:
    def __init__(
        self,
        *,
        db: Session,
        ctx: RequestContext,
        storage: StoragePort,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.storage = storage

    async def snapshot(self) -> DiagnosticsSnapshot:
        database = self._probe_database()
        storage = await self._probe_storage()
        dependencies = [database, storage]
        workspace = (
            self._workspace_snapshot()
            if database.status == "healthy"
            else WorkspaceDiagnostic()
        )
        return DiagnosticsSnapshot(
            generated_at=utc_now(),
            version=self._version(),
            environment=(settings.environment or "development").strip().lower(),
            overall_status=(
                "healthy"
                if all(item.status == "healthy" for item in dependencies)
                else "degraded"
            ),
            dependencies=dependencies,
            process=self._process_snapshot(),
            workspace=workspace,
        )

    def _probe_database(self) -> DependencyDiagnostic:
        started = perf_counter()
        try:
            self.db.execute(text("SELECT 1"))
            return DependencyDiagnostic(
                name="database",
                status="healthy",
                latency_ms=self._elapsed_ms(started),
            )
        except Exception as exc:
            return DependencyDiagnostic(
                name="database",
                status="unavailable",
                latency_ms=self._elapsed_ms(started),
                message=type(exc).__name__,
            )

    async def _probe_storage(self) -> DependencyDiagnostic:
        started = perf_counter()
        try:
            await self.storage.ensure_ready()
            return DependencyDiagnostic(
                name="object_storage",
                status="healthy",
                latency_ms=self._elapsed_ms(started),
            )
        except Exception as exc:
            return DependencyDiagnostic(
                name="object_storage",
                status="unavailable",
                latency_ms=self._elapsed_ms(started),
                message=type(exc).__name__,
            )

    def _workspace_snapshot(self) -> WorkspaceDiagnostic:
        scope = (
            Agent.tenant_id == self.ctx.tenant_id,
            Agent.workspace_id == self.ctx.workspace_id,
        )
        since = utc_now() - timedelta(hours=24)
        return WorkspaceDiagnostic(
            agents=self._count(Agent, *scope, Agent.deleted_at.is_(None)),
            workflows=self._count(
                Workflow,
                Workflow.tenant_id == self.ctx.tenant_id,
                Workflow.workspace_id == self.ctx.workspace_id,
                Workflow.deleted_at.is_(None),
            ),
            knowledge_bases=self._count(
                Knowledge,
                Knowledge.tenant_id == self.ctx.tenant_id,
                Knowledge.workspace_id == self.ctx.workspace_id,
                Knowledge.deleted_at.is_(None),
            ),
            plugins=self._count(
                Plugin,
                Plugin.tenant_id == self.ctx.tenant_id,
                Plugin.workspace_id == self.ctx.workspace_id,
            ),
            models=self._count(
                ProviderModel,
                ProviderModel.tenant_id == self.ctx.tenant_id,
                ProviderModel.workspace_id == self.ctx.workspace_id,
            ),
            threads=self._count(
                Thread,
                Thread.tenant_id == self.ctx.tenant_id,
                Thread.workspace_id == self.ctx.workspace_id,
                Thread.deleted_at.is_(None),
            ),
            active_runs=self._count(
                Run,
                Run.tenant_id == self.ctx.tenant_id,
                Run.workspace_id == self.ctx.workspace_id,
                Run.status.in_(("queued", "running", "paused")),
            ),
            failed_runs_24h=self._count(
                Run,
                Run.tenant_id == self.ctx.tenant_id,
                Run.workspace_id == self.ctx.workspace_id,
                Run.status == "failed",
                Run.created_at >= since,
            ),
            open_feedback=self._count(
                ProductFeedback,
                ProductFeedback.tenant_id == self.ctx.tenant_id,
                ProductFeedback.workspace_id == self.ctx.workspace_id,
                ProductFeedback.status.in_(("open", "in_progress")),
            ),
        )

    def _count(self, model, *filters) -> int:
        result = self.db.exec(select(func.count()).select_from(model).where(*filters)).one()
        if isinstance(result, tuple):
            return int(result[0])
        return int(result)

    @staticmethod
    def _process_snapshot() -> ProcessDiagnostic:
        process = psutil.Process()
        return ProcessDiagnostic(
            uptime_seconds=max(0, int(time() - process.create_time())),
            rss_bytes=int(process.memory_info().rss),
            thread_count=process.num_threads(),
        )

    @staticmethod
    def _version() -> str:
        try:
            return version("soit")
        except PackageNotFoundError:
            return "development"

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((perf_counter() - started) * 1000, 2)
