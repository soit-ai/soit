"""Knowledge application service backed by the unified knowledge runtime."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.trace.schemas import RunCostByModeResponse, RunCostSummaryResponse, RunResponse
from app.modules.knowledge.application.runtime_schemas import (
    KnowledgeConsumerUsageResponse,
    KnowledgeCreate,
    KnowledgeUpdate,
    ChunkUpdate,
    DocumentResponse,
    DocumentUpload,
    ChunkResponse,
    IndexCreate,
    IndexResponse,
    IndexUpdate,
    IngestTaskResponse,
    QueryRequest,
    QueryResponse,
)
from app.modules.knowledge.application.runtime_service import KnowledgeRuntimeService
from app.modules.knowledge.application.ports import (
    ChunkRepositoryPort,
    KnowledgeRepositoryPort,
    DocumentRepositoryPort,
    IndexRepositoryPort,
    IngestTaskRepositoryPort,
)
from app.modules.knowledge.runtime.index_builder import IndexBuilder
from app.modules.knowledge.runtime.pipeline import DocumentPipeline
from app.modules.knowledge.runtime.retrieval import RetrievalService
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.ports.vector.interface import VectorPort
from app.kernel.trace.writer import TraceWriter


class KnowledgeService:
    """First-class knowledge capability service.

    The persistence/runtime implementation continues to reuse the internal
    knowledge storage pipeline, but callers only depend on
    the knowledge boundary.
    """

    def __init__(
        self,
        *,
        db: Optional[Session] = None,
        ctx: Optional[RequestContext] = None,
        knowledge_repo: Optional[KnowledgeRepositoryPort] = None,
        document_repo: Optional[DocumentRepositoryPort] = None,
        chunk_repo: Optional[ChunkRepositoryPort] = None,
        index_repo: Optional[IndexRepositoryPort] = None,
        ingest_task_repo: Optional[IngestTaskRepositoryPort] = None,
        pipeline: Optional[DocumentPipeline] = None,
        retrieval_service: Optional[RetrievalService] = None,
        index_builder: Optional[IndexBuilder] = None,
        storage_port: Optional[StoragePort] = None,
        vector_port: Optional[VectorPort] = None,
        trace_writer: Optional[TraceWriter] = None,
        runtime_service: Optional[KnowledgeRuntimeService] = None,
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
        )

    def __getattr__(self, item: str):
        return getattr(self.runtime_service, item)

    async def create_knowledge(self, payload: KnowledgeCreate):
        return await self.runtime_service.create_knowledge(payload)

    async def list_knowledge(self, *, limit: int, offset: int):
        return await self.runtime_service.list_knowledge(limit=limit, offset=offset)

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

    async def list_applications(self, knowledge_id: str, *, limit: int) -> list[KnowledgeConsumerUsageResponse]:
        return await self.runtime_service.list_knowledge_app_usages(knowledge_id, limit=limit)

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
        file_content: bytes | None,
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
        status: Optional[str],
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
