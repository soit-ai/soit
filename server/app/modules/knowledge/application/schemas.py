"""Knowledge schemas backed by the knowledge-facing API surface."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field
from app.modules.knowledge.application.runtime_schemas import (
    ChunkResponse,
    ChunkUpdate,
    KnowledgeConsumerUsageResponse,
    DocumentResponse,
    DocumentUpload,
    IndexCreate,
    IndexResponse,
    IndexUpdate,
    IngestTaskResponse,
    QueryRequest,
    QueryResponse,
)


class KnowledgeCreateRequest(BaseModel):
    """Create a knowledge base without exposing legacy naming upstream."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    knowledge_type: str = Field(default="document", pattern="^(document|qa|code|graph|other)$")
    visibility: str = Field(default="private", pattern="^(private|workspace|tenant)$")
    settings_json: dict[str, Any] = Field(default_factory=dict)
    chunking_json: dict[str, Any] = Field(default_factory=dict)
    retrieval_json: dict[str, Any] = Field(default_factory=dict)
    default_embedding_model_ref: Optional[str] = None
    default_reranker_ref: Optional[str] = None
    tags: Optional[list[str]] = None


class KnowledgeUpdateRequest(BaseModel):
    """Update mutable knowledge base fields."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[str] = Field(default=None, pattern="^(active|archived|disabled)$")
    visibility: Optional[str] = Field(default=None, pattern="^(private|workspace|tenant)$")
    settings_json: Optional[dict[str, Any]] = None
    chunking_json: Optional[dict[str, Any]] = None
    retrieval_json: Optional[dict[str, Any]] = None
    default_embedding_model_ref: Optional[str] = None
    default_reranker_ref: Optional[str] = None
    tags: Optional[list[str]] = None


class KnowledgeResponse(BaseModel):
    """Knowledge base response schema."""

    id: str
    tenant_id: str
    workspace_id: str
    name: str
    description: Optional[str]
    status: str
    visibility: str
    knowledge_type: str
    source_type: str
    """Deprecated compatibility alias; mirrors `knowledge_type` during the migration window."""
    settings_json: dict[str, Any]
    chunking_json: dict[str, Any]
    retrieval_json: dict[str, Any]
    default_embedding_model_ref: Optional[str]
    default_reranker_ref: Optional[str]
    default_index_id: Optional[str]
    doc_count: int
    chunk_count: int
    last_ingested_at: Optional[datetime]
    last_indexed_at: Optional[datetime]
    tags: Optional[list[str]]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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


class KnowledgeBindingUsageResponse(KnowledgeConsumerUsageResponse):
    """Knowledge consumer binding response."""
