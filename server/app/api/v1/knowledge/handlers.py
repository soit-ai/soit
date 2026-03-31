"""Handlers for knowledge APIs."""

from __future__ import annotations

from typing import Optional

from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.contracts.context import RequestContext
from app.kernel.trace.schemas import (
    RunCostByModeResponse,
    RunCostSummaryResponse,
    RunResponse,
)
from app.modules.knowledge.application.runtime_schemas import KnowledgeCreate, KnowledgeUpdate
from app.modules.knowledge.application.schemas import (
    KnowledgeUsageResponse,
    KnowledgeChunkResponse,
    KnowledgeChunkUpdate,
    KnowledgeCreateRequest,
    KnowledgeDocumentResponse,
    KnowledgeDocumentUpload,
    KnowledgeIndexCreate,
    KnowledgeIndexResponse,
    KnowledgeIndexUpdate,
    KnowledgeIngestTaskResponse,
    KnowledgeQueryRequest,
    KnowledgeQueryResponse,
    KnowledgeResponse,
    KnowledgeUpdateRequest,
)
from app.modules.knowledge.application.service import KnowledgeService


class KnowledgeHandlers:
    """Thin orchestration for knowledge endpoints."""

    def __init__(self, service: KnowledgeService) -> None:
        self.service = service

    def _to_response(self, knowledge) -> KnowledgeResponse:
        return KnowledgeResponse(
            id=knowledge.id,
            tenant_id=knowledge.tenant_id,
            workspace_id=knowledge.workspace_id,
            name=knowledge.name,
            description=knowledge.description,
            status=knowledge.status,
            visibility=knowledge.visibility,
            knowledge_type=knowledge.type,
            settings_json=knowledge.settings_json or {},
            chunking_json=knowledge.chunking_json or {},
            retrieval_json=knowledge.retrieval_json or {},
            default_embedding_model_ref=knowledge.default_embedding_model_ref,
            default_reranker_ref=knowledge.default_reranker_ref,
            default_index_id=knowledge.default_index_id,
            doc_count=knowledge.doc_count,
            chunk_count=knowledge.chunk_count,
            last_ingested_at=knowledge.last_ingested_at,
            last_indexed_at=knowledge.last_indexed_at,
            tags=knowledge.tags,
            created_at=knowledge.created_at,
            updated_at=knowledge.updated_at,
        )

    def _to_knowledge_create(self, payload: KnowledgeCreateRequest) -> KnowledgeCreate:
        return KnowledgeCreate(
            name=payload.name,
            type=payload.knowledge_type,
            description=payload.description,
            visibility=payload.visibility,
            settings_json=payload.settings_json,
            chunking_json=payload.chunking_json,
            retrieval_json=payload.retrieval_json,
            default_embedding_model_ref=payload.default_embedding_model_ref,
            default_reranker_ref=payload.default_reranker_ref,
            tags=payload.tags,
        )

    def _to_knowledge_update(self, payload: KnowledgeUpdateRequest) -> KnowledgeUpdate:
        return KnowledgeUpdate(
            name=payload.name,
            description=payload.description,
            status=payload.status,
            visibility=payload.visibility,
            settings_json=payload.settings_json,
            chunking_json=payload.chunking_json,
            retrieval_json=payload.retrieval_json,
            default_embedding_model_ref=payload.default_embedding_model_ref,
            default_reranker_ref=payload.default_reranker_ref,
            tags=payload.tags,
        )

    async def create_knowledge(self, ctx: RequestContext, payload: KnowledgeCreateRequest) -> KnowledgeResponse:
        knowledge = await self.service.create_knowledge(self._to_knowledge_create(payload))
        return self._to_response(knowledge)

    async def list_knowledge(
        self,
        ctx: RequestContext,
        page_token: Optional[str],
        page_size: int,
    ) -> PaginatedResponse[KnowledgeResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        knowledge_items = await self.service.list_knowledge(limit=limit, offset=offset)
        items = [self._to_response(item) for item in knowledge_items]
        has_next = len(knowledge_items) == limit
        next_offset = offset + len(knowledge_items) if has_next else None
        return PaginatedResponse.create(items=items, page_size=len(items), has_next=has_next, next_offset=next_offset)

    async def get_knowledge(self, ctx: RequestContext, knowledge_id: str) -> KnowledgeResponse:
        knowledge = await self.service.get_knowledge(knowledge_id)
        return self._to_response(knowledge)

    async def update_knowledge(
        self,
        ctx: RequestContext,
        knowledge_id: str,
        payload: KnowledgeUpdateRequest,
    ) -> KnowledgeResponse:
        knowledge = await self.service.update_knowledge(knowledge_id, self._to_knowledge_update(payload))
        return self._to_response(knowledge)

    async def delete_knowledge(self, ctx: RequestContext, knowledge_id: str) -> None:
        await self.service.delete_knowledge(knowledge_id)

    async def list_documents(
        self,
        ctx: RequestContext,
        knowledge_id: str,
        limit: int,
        offset: int,
    ) -> list[DocumentResponse]:
        documents = await self.service.list_documents(knowledge_id, include_content=True, limit=limit, offset=offset)
        return [KnowledgeDocumentResponse.model_validate(item) for item in documents]

    async def list_runs(
        self,
        ctx: RequestContext,
        knowledge_id: str,
        page_token: Optional[str],
        page_size: int,
    ) -> PaginatedResponse[RunResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        runs = await self.service.list_runs(knowledge_id, limit=limit + 1, offset=offset)
        has_next = len(runs) > limit
        items = runs[:limit]
        next_offset = offset + len(items) if has_next else None
        return PaginatedResponse.create(
            items=[RunResponse.model_validate(item) for item in items],
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )

    async def summarize_costs(self, ctx: RequestContext, knowledge_id: str) -> RunCostSummaryResponse:
        return await self.service.summarize_costs(knowledge_id)

    async def summarize_costs_by_mode(
        self,
        ctx: RequestContext,
        knowledge_id: str,
    ) -> list[RunCostByModeResponse]:
        return await self.service.summarize_costs_by_mode(knowledge_id)

    async def list_usages(
        self,
        ctx: RequestContext,
        knowledge_id: str,
        limit: int,
    ) -> list[KnowledgeUsageResponse]:
        return await self.service.list_usages(knowledge_id, limit=limit)

    async def create_index(self, ctx: RequestContext, knowledge_id: str, payload: KnowledgeIndexCreate) -> KnowledgeIndexResponse:
        return KnowledgeIndexResponse.model_validate(await self.service.create_index(knowledge_id, payload))

    async def list_indexes(
        self,
        ctx: RequestContext,
        knowledge_id: str,
        limit: int,
        offset: int,
    ) -> list[KnowledgeIndexResponse]:
        indexes = await self.service.list_indexes(knowledge_id, limit=limit, offset=offset)
        return [KnowledgeIndexResponse.model_validate(item) for item in indexes]

    async def update_index(
        self,
        ctx: RequestContext,
        knowledge_id: str,
        index_id: str,
        payload: KnowledgeIndexUpdate,
    ) -> KnowledgeIndexResponse:
        return KnowledgeIndexResponse.model_validate(await self.service.update_index(knowledge_id, index_id, payload))

    async def delete_index(self, ctx: RequestContext, knowledge_id: str, index_id: str) -> None:
        await self.service.delete_index(knowledge_id, index_id)

    async def rebuild_index(self, ctx: RequestContext, knowledge_id: str, index_id: str) -> KnowledgeIndexResponse:
        return KnowledgeIndexResponse.model_validate(await self.service.rebuild_index(knowledge_id, index_id))

    async def upload_document(
        self,
        ctx: RequestContext,
        knowledge_id: str,
        payload: KnowledgeDocumentUpload,
        file_content: bytes | None,
        *,
        async_ingest: bool,
        max_retries: int,
    ) -> KnowledgeDocumentResponse:
        return KnowledgeDocumentResponse.model_validate(
            await self.service.upload_document(
                knowledge_id,
                payload,
                file_content,
                async_ingest=async_ingest,
                max_retries=max_retries,
            )
        )

    async def get_document(self, ctx: RequestContext, document_id: str) -> KnowledgeDocumentResponse:
        return KnowledgeDocumentResponse.model_validate(await self.service.get_document(document_id))

    async def list_document_versions(self, ctx: RequestContext, knowledge_id: str, doc_key: str) -> list[KnowledgeDocumentResponse]:
        versions = await self.service.list_document_versions(knowledge_id, doc_key)
        return [KnowledgeDocumentResponse.model_validate(item) for item in versions]

    async def rollback_document_version(
        self,
        ctx: RequestContext,
        knowledge_id: str,
        doc_key: str,
        version: int,
    ) -> KnowledgeDocumentResponse:
        return KnowledgeDocumentResponse.model_validate(await self.service.rollback_document_version(knowledge_id, doc_key, version))

    async def delete_document(self, ctx: RequestContext, document_id: str) -> None:
        await self.service.delete_document(document_id)

    async def list_chunks(
        self,
        ctx: RequestContext,
        knowledge_id: str,
        document_id: str,
        limit: int,
        offset: int,
    ) -> list[KnowledgeChunkResponse]:
        chunks = await self.service.list_chunks(knowledge_id, document_id, limit=limit, offset=offset)
        return [KnowledgeChunkResponse.model_validate(item) for item in chunks]

    async def update_chunk(
        self,
        ctx: RequestContext,
        knowledge_id: str,
        document_id: str,
        chunk_id: str,
        payload: KnowledgeChunkUpdate,
    ) -> KnowledgeChunkResponse:
        return KnowledgeChunkResponse.model_validate(await self.service.update_chunk(knowledge_id, document_id, chunk_id, payload))

    async def list_ingest_tasks(
        self,
        ctx: RequestContext,
        knowledge_id: str,
        status: Optional[str],
        limit: int,
        offset: int,
    ) -> list[KnowledgeIngestTaskResponse]:
        tasks = await self.service.list_ingest_tasks(knowledge_id, status=status, limit=limit, offset=offset)
        return [KnowledgeIngestTaskResponse.model_validate(item) for item in tasks]

    async def get_ingest_task(self, ctx: RequestContext, knowledge_id: str, task_id: str) -> KnowledgeIngestTaskResponse:
        return KnowledgeIngestTaskResponse.model_validate(await self.service.get_ingest_task(knowledge_id, task_id))

    async def retry_ingest_task(self, ctx: RequestContext, knowledge_id: str, task_id: str) -> KnowledgeIngestTaskResponse:
        return KnowledgeIngestTaskResponse.model_validate(await self.service.retry_ingest_task(knowledge_id, task_id))

    async def cancel_ingest_task(self, ctx: RequestContext, knowledge_id: str, task_id: str) -> KnowledgeIngestTaskResponse:
        return KnowledgeIngestTaskResponse.model_validate(await self.service.cancel_ingest_task(knowledge_id, task_id))

    async def retry_document_ingest(
        self,
        ctx: RequestContext,
        knowledge_id: str,
        document_id: str,
        max_retries: int,
    ) -> KnowledgeIngestTaskResponse:
        return KnowledgeIngestTaskResponse.model_validate(
            await self.service.retry_document_ingest(knowledge_id, document_id, max_retries=max_retries)
        )

    async def query(self, ctx: RequestContext, knowledge_id: str, payload: KnowledgeQueryRequest) -> KnowledgeQueryResponse:
        return await self.service.query(knowledge_id, payload)
