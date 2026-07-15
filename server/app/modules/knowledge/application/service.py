"""Knowledge application service backed by the unified knowledge runtime."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.pagination import PageToken
from app.kernel.identity.guard import workspace_guard
from app.kernel.ports.http.interface import HttpFetchPort
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.ports.vector.interface import VectorPort
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.runs.schemas import (
    RunCostByModeResponse,
    RunCostSummaryResponse,
    RunResponse,
)
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.knowledge.application.ports import (
    ChunkRepositoryPort,
    DocumentRepositoryPort,
    IndexRepositoryPort,
    IngestTaskRepositoryPort,
    KnowledgeRepositoryPort,
)
from app.modules.knowledge.application.runtime_schemas import (
    ChunkResponse,
    ChunkUpdate,
    DocumentResponse,
    DocumentUpload,
    IndexCreate,
    IndexResponse,
    IndexUpdate,
    IngestTaskResponse,
    KnowledgeConsumerUsageResponse,
    KnowledgeCreate,
    KnowledgeUpdate,
    QueryRequest,
    QueryResponse,
)
from app.modules.knowledge.application.runtime_service import KnowledgeRuntimeService
from app.modules.knowledge.application.schemas import (
    KnowledgeWorkbenchItemsResponse,
    KnowledgeWorkbenchResponse,
    KnowledgeWorkbenchRow,
    KnowledgeWorkbenchSummary,
    KnowledgeWorkbenchTabs,
)
from app.modules.knowledge.domain.models import (
    Knowledge,
    KnowledgeDocument,
    KnowledgeIndex,
    KnowledgeIngestTask,
)
from app.modules.knowledge.runtime.index_builder import IndexBuilder
from app.modules.knowledge.runtime.pipeline import DocumentPipeline
from app.modules.knowledge.runtime.retrieval import RetrievalService


class KnowledgeService:
    """First-class knowledge capability service.

    The persistence/runtime implementation continues to reuse the internal
    knowledge storage pipeline, but callers only depend on
    the knowledge boundary.
    """

    def __init__(
        self,
        *,
        db: Session | None = None,
        ctx: RequestContext | None = None,
        knowledge_repo: KnowledgeRepositoryPort | None = None,
        document_repo: DocumentRepositoryPort | None = None,
        chunk_repo: ChunkRepositoryPort | None = None,
        index_repo: IndexRepositoryPort | None = None,
        ingest_task_repo: IngestTaskRepositoryPort | None = None,
        pipeline: DocumentPipeline | None = None,
        retrieval_service: RetrievalService | None = None,
        index_builder: IndexBuilder | None = None,
        storage_port: StoragePort | None = None,
        vector_port: VectorPort | None = None,
        trace_writer: TraceWriter | None = None,
        http_fetch_port: HttpFetchPort | None = None,
        runtime_service: KnowledgeRuntimeService | None = None,
    ) -> None:
        self.runtime_service = runtime_service or KnowledgeRuntimeService(
            db=db,
            ctx=ctx,
            knowledge_repo=knowledge_repo,
            document_repo=document_repo,
            chunk_repo=chunk_repo,
            index_repo=index_repo,
            ingest_task_repo=ingest_task_repo,
            pipeline=pipeline,
            retrieval_service=retrieval_service,
            index_builder=index_builder,
            storage_port=storage_port,
            vector_port=vector_port,
            trace_writer=trace_writer,
            http_fetch_port=http_fetch_port,
        )
        self.db = self.runtime_service.db
        self.ctx = self.runtime_service.ctx

    def __getattr__(self, item: str):
        return getattr(self.runtime_service, item)

    async def create_knowledge(self, payload: KnowledgeCreate):
        return await self.runtime_service.create_knowledge(payload)

    async def list_knowledge(self, *, limit: int, offset: int):
        return await self.runtime_service.list_knowledge(limit=limit, offset=offset)

    @workspace_guard("read")
    async def get_workbench(self, *, limit: int, offset: int) -> KnowledgeWorkbenchResponse:
        rows, runs_by_knowledge = self._build_workbench_rows()
        all_today_runs = [
            run
            for knowledge_runs in runs_by_knowledge.values()
            for run in knowledge_runs
            if self._is_today(run.started_at)
        ]
        summary = KnowledgeWorkbenchSummary(
            total_knowledge_bases=len(rows),
            ready_knowledge_bases=sum(1 for row in rows if row.status == "ready"),
            total_documents=sum(row.document_count for row in rows),
            total_chunks=sum(row.chunk_count for row in rows),
            today_calls=len(all_today_runs),
            avg_latency_ms=self._average_latency(all_today_runs),
            hit_rate=self._success_rate(all_today_runs),
            recent_exceptions=sum(1 for run in all_today_runs if self._run_failed(run)),
            updated_at=utc_now(),
        )
        tabs = KnowledgeWorkbenchTabs(
            all=len(rows),
            high_volume=sum(1 for row in rows if row.today_calls >= 100),
            low_hit=sum(1 for row in rows if row.hit_rate is not None and row.hit_rate < 95),
            slow=sum(1 for row in rows if row.status in {"indexing", "error"} or (row.avg_latency_ms is not None and row.avg_latency_ms >= 2000)),
            unconfigured=sum(1 for row in rows if row.status == "unconfigured"),
        )
        visible_rows = rows[offset: offset + limit]
        has_next = offset + len(visible_rows) < len(rows)
        next_page_token = PageToken(offset=offset + len(visible_rows), limit=limit).to_string() if has_next else None
        return KnowledgeWorkbenchResponse(
            summary=summary,
            tabs=tabs,
            items=visible_rows,
            next_page_token=next_page_token,
            page_size=len(visible_rows),
        )

    @workspace_guard("read")
    async def get_workbench_items(
        self,
        *,
        limit: int,
        offset: int,
        tab: str | None = None,
        keyword: str | None = None,
    ) -> KnowledgeWorkbenchItemsResponse:
        rows, _ = self._build_workbench_rows()
        filtered_rows = self._filter_workbench_rows(rows, tab=tab, keyword=keyword)
        visible_rows = filtered_rows[offset: offset + limit]
        has_next = offset + len(visible_rows) < len(filtered_rows)
        next_page_token = PageToken(offset=offset + len(visible_rows), limit=limit).to_string() if has_next else None
        return KnowledgeWorkbenchItemsResponse(
            items=visible_rows,
            next_page_token=next_page_token,
            page_size=len(visible_rows),
        )

    def _build_workbench_rows(self) -> tuple[list[KnowledgeWorkbenchRow], dict[str, list[Run]]]:
        knowledge_items = self._list_workbench_knowledge()
        knowledge_base_ids = [knowledge.id for knowledge in knowledge_items]
        runs_by_knowledge = self._workbench_runs_by_knowledge(knowledge_base_ids)
        indexes_by_knowledge = self._workbench_indexes_by_knowledge(knowledge_base_ids)
        tasks_by_knowledge = self._workbench_tasks_by_knowledge(knowledge_base_ids)
        sources_by_knowledge = self._workbench_sources_by_knowledge(knowledge_base_ids)
        rows = [
            self._build_workbench_row(
                knowledge,
                runs_by_knowledge.get(knowledge.id, []),
                indexes_by_knowledge.get(knowledge.id, []),
                tasks_by_knowledge.get(knowledge.id, []),
                sources_by_knowledge.get(knowledge.id, []),
            )
            for knowledge in knowledge_items
        ]
        return rows, runs_by_knowledge

    def _filter_workbench_rows(
        self,
        rows: list[KnowledgeWorkbenchRow],
        *,
        tab: str | None,
        keyword: str | None,
    ) -> list[KnowledgeWorkbenchRow]:
        normalized_tab = (tab or "all").strip().lower()
        normalized_keyword = (keyword or "").strip().lower()

        def tab_matches(row: KnowledgeWorkbenchRow) -> bool:
            if normalized_tab in {"", "all"}:
                return True
            if normalized_tab == "high":
                return row.today_calls >= 100
            if normalized_tab == "low-hit":
                return row.hit_rate is not None and row.hit_rate < 95
            if normalized_tab == "slow":
                return row.status in {"indexing", "error"} or (row.avg_latency_ms is not None and row.avg_latency_ms >= 2000)
            return row.status == normalized_tab

        def keyword_matches(row: KnowledgeWorkbenchRow) -> bool:
            if not normalized_keyword:
                return True
            haystack = " ".join(
                filter(
                    None,
                    [
                        row.name,
                        row.description,
                        row.owner,
                        row.status,
                        row.knowledge_type,
                        row.content_source,
                    ],
                )
            ).lower()
            return normalized_keyword in haystack

        return [row for row in rows if tab_matches(row) and keyword_matches(row)]

    def _list_workbench_knowledge(self) -> list[Knowledge]:
        query = (
            select(Knowledge)
            .where(
                and_(
                    Knowledge.tenant_id == self.ctx.tenant_id,
                    Knowledge.workspace_id == self.ctx.workspace_id,
                    Knowledge.deleted_at.is_(None),
                )
            )
            .order_by(desc(Knowledge.updated_at))
        )
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, Knowledge) else item[0] for item in results]

    def _workbench_runs_by_knowledge(self, knowledge_base_ids: list[str]) -> dict[str, list[Run]]:
        if not knowledge_base_ids:
            return {}
        query = (
            select(Run)
            .where(
                and_(
                    Run.tenant_id == self.ctx.tenant_id,
                    Run.workspace_id == self.ctx.workspace_id,
                    Run.subject_kind == "knowledge",
                    Run.subject_id.in_(knowledge_base_ids),
                )
            )
            .order_by(desc(Run.started_at))
        )
        results = list(self.db.exec(query).all())
        grouped: dict[str, list[Run]] = defaultdict(list)
        for item in results:
            run = item if isinstance(item, Run) else item[0]
            if run.subject_id:
                grouped[run.subject_id].append(run)
        return grouped

    def _workbench_indexes_by_knowledge(self, knowledge_base_ids: list[str]) -> dict[str, list[KnowledgeIndex]]:
        if not knowledge_base_ids:
            return {}
        query = (
            select(KnowledgeIndex)
            .where(
                and_(
                    KnowledgeIndex.tenant_id == self.ctx.tenant_id,
                    KnowledgeIndex.workspace_id == self.ctx.workspace_id,
                    KnowledgeIndex.knowledge_id.in_(knowledge_base_ids),
                    KnowledgeIndex.deleted_at.is_(None),
                )
            )
            .order_by(desc(KnowledgeIndex.updated_at))
        )
        results = list(self.db.exec(query).all())
        grouped: dict[str, list[KnowledgeIndex]] = defaultdict(list)
        for item in results:
            index = item if isinstance(item, KnowledgeIndex) else item[0]
            grouped[index.knowledge_id].append(index)
        return grouped

    def _workbench_tasks_by_knowledge(self, knowledge_base_ids: list[str]) -> dict[str, list[KnowledgeIngestTask]]:
        if not knowledge_base_ids:
            return {}
        query = (
            select(KnowledgeIngestTask)
            .where(
                and_(
                    KnowledgeIngestTask.tenant_id == self.ctx.tenant_id,
                    KnowledgeIngestTask.workspace_id == self.ctx.workspace_id,
                    KnowledgeIngestTask.knowledge_id.in_(knowledge_base_ids),
                )
            )
            .order_by(desc(KnowledgeIngestTask.updated_at))
        )
        results = list(self.db.exec(query).all())
        grouped: dict[str, list[KnowledgeIngestTask]] = defaultdict(list)
        for item in results:
            task = item if isinstance(item, KnowledgeIngestTask) else item[0]
            grouped[task.knowledge_id].append(task)
        return grouped

    def _workbench_sources_by_knowledge(self, knowledge_base_ids: list[str]) -> dict[str, list[str]]:
        if not knowledge_base_ids:
            return {}
        query = (
            select(KnowledgeDocument)
            .where(
                and_(
                    KnowledgeDocument.tenant_id == self.ctx.tenant_id,
                    KnowledgeDocument.workspace_id == self.ctx.workspace_id,
                    KnowledgeDocument.knowledge_id.in_(knowledge_base_ids),
                    KnowledgeDocument.is_latest.is_(True),
                    KnowledgeDocument.deleted_at.is_(None),
                )
            )
            .order_by(desc(KnowledgeDocument.updated_at))
        )
        results = list(self.db.exec(query).all())
        grouped: dict[str, list[str]] = defaultdict(list)
        for item in results:
            document = item if isinstance(item, KnowledgeDocument) else item[0]
            if document.source_kind and document.source_kind not in grouped[document.knowledge_id]:
                grouped[document.knowledge_id].append(document.source_kind)
        return grouped

    def _build_workbench_row(
        self,
        knowledge: Knowledge,
        runs: list[Run],
        indexes: list[KnowledgeIndex],
        tasks: list[KnowledgeIngestTask],
        sources: list[str],
    ) -> KnowledgeWorkbenchRow:
        today_runs = [run for run in runs if self._is_today(run.started_at)]
        metric_runs = today_runs if today_runs else runs
        avg_latency_ms = self._average_latency(metric_runs)
        hit_rate = self._success_rate(metric_runs)
        exception_count = sum(1 for run in metric_runs if self._run_failed(run))
        return KnowledgeWorkbenchRow(
            id=knowledge.id,
            name=knowledge.name,
            description=knowledge.description,
            status=self._resolve_workbench_status(knowledge, indexes, tasks, exception_count, hit_rate),
            knowledge_type=knowledge.type,
            content_source=self._format_content_source(knowledge, sources),
            document_count=knowledge.doc_count,
            chunk_count=knowledge.chunk_count,
            today_calls=len(today_runs),
            avg_latency_ms=avg_latency_ms,
            hit_rate=hit_rate,
            recent_exception_count=exception_count,
            owner=knowledge.updated_by or knowledge.created_by,
            last_sync_at=knowledge.last_indexed_at or knowledge.last_ingested_at,
            action_enabled=knowledge.status == "active" and knowledge.chunk_count > 0,
            updated_at=knowledge.updated_at,
        )

    def _resolve_workbench_status(
        self,
        knowledge: Knowledge,
        indexes: list[KnowledgeIndex],
        tasks: list[KnowledgeIngestTask],
        exception_count: int,
        hit_rate: float | None,
    ) -> str:
        if knowledge.status != "active":
            return "unconfigured"
        if any(index.status == "failed" for index in indexes) or any(task.status == "failed" for task in tasks):
            return "error"
        if exception_count > 0 or (hit_rate is not None and hit_rate < 90):
            return "error"
        if any(index.status == "building" for index in indexes) or any(task.status in {"queued", "running"} for task in tasks):
            return "indexing"
        if knowledge.last_ingested_at and (not knowledge.last_indexed_at or knowledge.last_ingested_at > knowledge.last_indexed_at):
            return "indexing"
        if knowledge.doc_count <= 0 or knowledge.chunk_count <= 0:
            return "unconfigured"
        if not any(index.status == "ready" for index in indexes) and not knowledge.default_index_id:
            return "unconfigured"
        return "ready"

    def _format_content_source(self, knowledge: Knowledge, sources: list[str]) -> str:
        if sources:
            return " / ".join(source.replace("_", " ").title() for source in sources[:2])
        settings = knowledge.settings_json or {}
        source = settings.get("source_kind") if isinstance(settings, dict) else None
        if isinstance(source, str) and source.strip():
            return source.replace("_", " ").title()
        return knowledge.type.replace("_", " ").title()

    def _is_today(self, value) -> bool:
        if value is None:
            return False
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        return value >= start

    def _average_latency(self, runs: list[Run]) -> int | None:
        durations = [run.duration_ms for run in runs if run.duration_ms is not None]
        if not durations:
            return None
        return int(round(sum(durations) / len(durations)))

    def _success_rate(self, runs: list[Run]) -> float | None:
        if not runs:
            return None
        successes = sum(1 for run in runs if run.status in {"succeeded", "completed"})
        return round((successes / len(runs)) * 100, 1)

    def _run_failed(self, run: Run) -> bool:
        return run.status in {"failed", "error"} or bool(run.error_code or run.error_message)

    async def get_knowledge(self, knowledge_id: str):
        return await self.runtime_service.get_knowledge(knowledge_id)

    async def update_knowledge(self, knowledge_id: str, payload: KnowledgeUpdate):
        return await self.runtime_service.update_knowledge(knowledge_id, payload)

    async def delete_knowledge(self, knowledge_id: str) -> None:
        await self.runtime_service.delete_knowledge(knowledge_id)

    async def list_documents(self, knowledge_id: str, *, include_content: bool, limit: int, offset: int) -> list[DocumentResponse]:
        return await self.runtime_service.list_documents(knowledge_id, include_content, limit, offset)

    async def list_runs(self, knowledge_id: str, *, limit: int, offset: int) -> list[RunResponse]:
        return await self.runtime_service.list_runs_for_knowledge(knowledge_id, limit=limit, offset=offset)

    async def summarize_costs(self, knowledge_id: str) -> RunCostSummaryResponse:
        return await self.runtime_service.summarize_run_costs_for_knowledge(knowledge_id)

    async def summarize_costs_by_mode(self, knowledge_id: str) -> list[RunCostByModeResponse]:
        return await self.runtime_service.summarize_run_costs_by_mode_for_knowledge(knowledge_id)

    async def list_usages(self, knowledge_id: str, *, limit: int) -> list[KnowledgeConsumerUsageResponse]:
        return await self.runtime_service.list_knowledge_usages(knowledge_id, limit=limit)

    async def create_index(self, knowledge_id: str, payload: IndexCreate):
        return await self.runtime_service.create_index(knowledge_id, payload)

    async def list_indexes(self, knowledge_id: str, *, limit: int, offset: int) -> list[IndexResponse]:
        return await self.runtime_service.list_indexes(knowledge_id, limit=limit, offset=offset)

    async def update_index(self, knowledge_id: str, index_id: str, payload: IndexUpdate):
        return await self.runtime_service.update_index(knowledge_id, index_id, payload)

    async def delete_index(self, knowledge_id: str, index_id: str) -> None:
        await self.runtime_service.delete_index(knowledge_id, index_id)

    async def rebuild_index(self, knowledge_id: str, index_id: str):
        return await self.runtime_service.rebuild_index(knowledge_id, index_id)

    async def upload_document(
        self,
        knowledge_id: str,
        payload: DocumentUpload,
        file_content: object | None,
        *,
        async_ingest: bool,
        max_retries: int,
    ) -> DocumentResponse:
        return await self.runtime_service.upload_document(
            knowledge_id,
            payload,
            file_content=file_content,
            async_ingest=async_ingest,
            max_retries=max_retries,
        )

    async def get_document(self, document_id: str):
        return await self.runtime_service.get_document(document_id)

    async def get_document_content(self, knowledge_id: str, document_id: str) -> tuple[bytes, str]:
        return await self.runtime_service.get_document_content(knowledge_id, document_id)

    async def download_document(self, knowledge_id: str, document_id: str) -> tuple[bytes, str, str]:
        return await self.runtime_service.download_document(knowledge_id, document_id)

    async def list_document_versions(self, knowledge_id: str, doc_key: str) -> list[DocumentResponse]:
        return await self.runtime_service.list_document_versions(knowledge_id, doc_key)

    async def rollback_document_version(self, knowledge_id: str, doc_key: str, version: int):
        return await self.runtime_service.rollback_document_version(knowledge_id, doc_key, version)

    async def delete_document(self, document_id: str) -> None:
        await self.runtime_service.delete_document(document_id)

    async def list_chunks(self, knowledge_id: str, document_id: str, *, limit: int, offset: int) -> list[ChunkResponse]:
        return await self.runtime_service.list_chunks(knowledge_id, document_id, limit, offset)

    async def update_chunk(self, knowledge_id: str, document_id: str, chunk_id: str, payload: ChunkUpdate):
        return await self.runtime_service.update_chunk(
            knowledge_id,
            document_id,
            chunk_id,
            content=payload.content,
            index_status=payload.index_status,
        )

    async def list_ingest_tasks(
        self,
        knowledge_id: str,
        *,
        status: str | None,
        limit: int,
        offset: int,
    ) -> list[IngestTaskResponse]:
        return await self.runtime_service.list_ingest_tasks(knowledge_id, status=status, limit=limit, offset=offset)

    async def get_ingest_task(self, knowledge_id: str, task_id: str):
        return await self.runtime_service.get_ingest_task(knowledge_id, task_id)

    async def retry_ingest_task(self, knowledge_id: str, task_id: str):
        return await self.runtime_service.retry_ingest_task(knowledge_id, task_id)

    async def cancel_ingest_task(self, knowledge_id: str, task_id: str):
        return await self.runtime_service.cancel_ingest_task(knowledge_id, task_id)

    async def retry_document_ingest(self, knowledge_id: str, document_id: str, *, max_retries: int = 1):
        return await self.runtime_service.retry_document_ingest(knowledge_id, document_id, max_retries=max_retries)

    async def query(self, knowledge_id: str, payload: QueryRequest) -> QueryResponse:
        return await self.runtime_service.query(knowledge_id, payload)
