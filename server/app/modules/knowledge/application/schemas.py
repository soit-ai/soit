"""Knowledge schemas backed by the knowledge-facing API surface."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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
    QueryRequest,
    QueryResponse,
)


class KnowledgeCreateRequest(BaseModel):
    """Create a knowledge base without exposing internal runtime naming upstream."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    knowledge_type: str = Field(default="document", pattern="^(document|qa|code|graph|other)$")
    visibility: str = Field(default="private", pattern="^(private|workspace|tenant)$")
    settings_json: dict[str, Any] = Field(default_factory=dict)
    chunking_json: dict[str, Any] = Field(default_factory=dict)
    retrieval_json: dict[str, Any] = Field(default_factory=dict)
    default_embedding_model_ref: str | None = None
    default_reranker_ref: str | None = None
    tags: list[str] | None = None


class KnowledgeUpdateRequest(BaseModel):
    """Update mutable knowledge base fields."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(default=None, pattern="^(active|archived|disabled)$")
    visibility: str | None = Field(default=None, pattern="^(private|workspace|tenant)$")
    settings_json: dict[str, Any] | None = None
    chunking_json: dict[str, Any] | None = None
    retrieval_json: dict[str, Any] | None = None
    default_embedding_model_ref: str | None = None
    default_reranker_ref: str | None = None
    tags: list[str] | None = None


class KnowledgeResponse(BaseModel):
    """Knowledge base response schema."""

    id: str
    tenant_id: str
    workspace_id: str
    name: str
    description: str | None
    status: str
    visibility: str
    knowledge_type: str
    settings_json: dict[str, Any]
    chunking_json: dict[str, Any]
    retrieval_json: dict[str, Any]
    default_embedding_model_ref: str | None
    default_reranker_ref: str | None
    default_index_id: str | None
    doc_count: int
    chunk_count: int
    last_ingested_at: datetime | None
    last_indexed_at: datetime | None
    tags: list[str] | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeWorkbenchSummary(BaseModel):
    """Knowledge workbench aggregate metrics."""

    total_knowledge_bases: int
    ready_knowledge_bases: int
    total_documents: int
    total_chunks: int
    today_calls: int
    avg_latency_ms: int | None
    hit_rate: float | None
    recent_exceptions: int
    updated_at: datetime


class KnowledgeWorkbenchTabs(BaseModel):
    """Counts for Knowledge workbench filter tabs."""

    all: int
    high_volume: int
    low_hit: int
    slow: int
    unconfigured: int


class KnowledgeWorkbenchRow(BaseModel):
    """Knowledge base row with indexing and retrieval health."""

    id: str
    name: str
    description: str | None
    status: str
    knowledge_type: str
    content_source: str
    document_count: int
    chunk_count: int
    today_calls: int
    avg_latency_ms: int | None
    hit_rate: float | None
    recent_exception_count: int
    owner: str | None
    last_sync_at: datetime | None
    action_enabled: bool
    updated_at: datetime


class KnowledgeWorkbenchResponse(BaseModel):
    """Full Knowledge workbench response."""

    summary: KnowledgeWorkbenchSummary
    tabs: KnowledgeWorkbenchTabs
    items: list[KnowledgeWorkbenchRow]
    next_page_token: str | None = None
    page_size: int


class KnowledgeWorkbenchItemsResponse(BaseModel):
    """Paginated Knowledge workbench table rows."""

    items: list[KnowledgeWorkbenchRow]
    next_page_token: str | None = None
    page_size: int


class KnowledgeDocumentUpload(DocumentUpload):
    """Knowledge document upload payload."""


class KnowledgeDocumentResponse(DocumentResponse):
    """Knowledge document response."""


class KnowledgeChunkResponse(ChunkResponse):
    """Knowledge chunk response."""


class KnowledgeChunkUpdate(ChunkUpdate):
    """Knowledge chunk update payload."""


class KnowledgeIndexCreate(IndexCreate):
    """Knowledge index creation payload."""


class KnowledgeIndexUpdate(IndexUpdate):
    """Knowledge index update payload."""


class KnowledgeIndexResponse(IndexResponse):
    """Knowledge index response."""


class KnowledgeIngestTaskResponse(IngestTaskResponse):
    """Knowledge ingest task response."""


class KnowledgeQueryRequest(QueryRequest):
    """Knowledge retrieval request."""


class KnowledgeQueryResponse(QueryResponse):
    """Knowledge retrieval response."""


class KnowledgeUsageResponse(KnowledgeConsumerUsageResponse):
    """Knowledge usage response."""
