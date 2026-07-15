""" schemas

Knowledge domain Pydantic schemas.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeCreate(BaseModel):
    """Schema for creating a knowledge base."""

    name: str = Field(..., min_length=1, max_length=255)
    """Knowledge name."""

    type: str = Field(..., pattern="^(document|qa|code|graph|other)$")
    """Knowledge type."""

    description: str | None = Field(None, max_length=1000)
    """Knowledge description."""

    visibility: str = Field(default="private", pattern="^(private|workspace|tenant)$")
    """Visibility."""

    settings_json: dict[str, Any] | None = Field(default_factory=dict)
    """General settings."""

    chunking_json: dict[str, Any] | None = Field(default_factory=dict)
    """Chunking strategy."""

    retrieval_json: dict[str, Any] | None = Field(default_factory=dict)
    """Retrieval strategy."""

    default_embedding_model_ref: str | None = Field(None)
    """Default embedding model."""

    default_reranker_ref: str | None = Field(None)
    """Default reranker."""

    tags: list[str] | None = Field(None)
    """Tags."""


class KnowledgeUpdate(BaseModel):
    """Schema for updating a knowledge base."""

    name: str | None = Field(None, min_length=1, max_length=255)
    """Knowledge name."""

    description: str | None = Field(None, max_length=1000)
    """Knowledge description."""

    status: str | None = Field(None, pattern="^(active|archived|disabled)$")
    """Status."""

    visibility: str | None = Field(None, pattern="^(private|workspace|tenant)$")
    """Visibility."""

    settings_json: dict[str, Any] | None = None
    """General settings."""

    chunking_json: dict[str, Any] | None = None
    """Chunking strategy."""

    retrieval_json: dict[str, Any] | None = None
    """Retrieval strategy."""

    default_embedding_model_ref: str | None = None
    """Default embedding model."""

    default_reranker_ref: str | None = None
    """Default reranker."""

    tags: list[str] | None = None
    """Tags."""


class DocumentUpload(BaseModel):
    """Schema for uploading a document."""

    doc_key: str = Field(..., min_length=1)
    """Document key."""

    source_kind: str = Field(..., pattern="^(upload|crawler|api|manual)$")
    """Source kind."""

    source_uri: str | None = None
    """Source URI."""

    file_id: str | None = None
    """File ID."""

    filename: str | None = None
    """Original filename."""

    mime_type: str | None = None
    """MIME type."""

    size_bytes: int | None = None
    """File size in bytes."""

    checksum: str | None = None
    """File checksum (sha256)."""

    content_hash: str | None = None
    """Content hash (sha256)."""

    title: str | None = None
    """Title."""

    language: str | None = None
    """Language."""

    access_policy_json: dict[str, Any] | None = Field(default_factory=dict)
    """Access policy."""


class QueryRequest(BaseModel):
    """Schema for querying knowledge."""

    query: str = Field(..., min_length=1)
    """Query text."""

    top_k: int = Field(default=10, ge=1, le=100)
    """Number of results."""

    index_id: str | None = None
    """Index ID (use default if not specified)."""

    filter: dict[str, Any] | None = None
    """Metadata filter."""

    use_rerank: bool = Field(default=False)
    """Use reranking."""

    reranker_ref: str | None = None
    """Reranker reference."""

    strategy: str | None = Field(default=None, pattern="^(vector|multi_index|keyword|hybrid)$")
    """Retrieval strategy."""

    index_ids: list[str] | None = None
    """Index IDs for multi-index retrieval."""

    keyword_top_k: int | None = Field(default=None, ge=1, le=200)
    """Top K for keyword retrieval."""

    keyword_candidate_limit: int | None = Field(default=None, ge=10, le=10000)
    """Max chunks to scan for keyword retrieval."""

    keyword_min_score: int | None = Field(default=None, ge=1)
    """Minimum keyword score to include a chunk."""

    hybrid_alpha: float | None = Field(default=None, ge=0.0, le=1.0)
    """Weight for vector scores in hybrid retrieval."""

    include_snippets: bool = Field(default=True)
    """Whether to include text snippets in results."""

    snippet_length: int = Field(default=160, ge=40, le=1000)
    """Snippet length for citations."""

    max_snippets: int = Field(default=2, ge=0, le=10)
    """Max snippets per result."""


class QueryResult(BaseModel):
    """Schema for query result."""

    chunk_id: str
    """Chunk ID."""

    document_id: str
    """Document ID."""

    score: float
    """Similarity score."""

    text: str
    """Chunk text."""

    snippets: list[str] = Field(default_factory=list)
    """Snippet list for citations."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Chunk metadata."""


class QueryCitation(BaseModel):
    """Schema for query citations."""

    chunk_id: str
    """Chunk ID."""

    document_id: str
    """Document ID."""

    rank: int
    """Rank in results."""

    score: float
    """Score used for ranking."""

    knowledge_id: str | None = None
    """Knowledge ID."""

    doc_key: str | None = None
    """Document key."""

    title: str | None = None
    """Document title."""

    source_uri: str | None = None
    """Source URI."""

    chunk_no: int | None = None
    """Chunk number."""

    page_no: int | None = None
    """Page number."""

    section_path: list[str] | None = None
    """Section path."""

    snippet: str | None = None
    """Primary snippet."""


class QueryResponse(BaseModel):
    """Schema for query response."""

    results: list[QueryResult]
    """Query results."""

    total: int
    """Total results count."""

    citations: list[QueryCitation] = Field(default_factory=list)
    """Citation list (sources + snippets)."""


class KnowledgeResponse(BaseModel):
    """Schema for knowledge response."""

    id: str
    tenant_id: str
    workspace_id: str
    name: str
    type: str
    description: str | None
    status: str
    visibility: str
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


class DocumentResponse(BaseModel):
    """Schema for document response."""

    id: str
    tenant_id: str
    workspace_id: str
    knowledge_id: str
    doc_key: str
    version: int
    is_latest: bool
    source_kind: str
    title: str | None
    language: str | None
    mime_type: str | None
    filename: str | None
    size_bytes: int | None
    checksum: str | None
    content_hash: str | None
    source_uri: str | None
    file_id: str | None
    error_code: str | None
    error_message: str | None
    retry_count: int
    status: str
    parse_meta_json: dict[str, Any] = Field(default_factory=dict)
    index_meta_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ChunkResponse(BaseModel):
    """Schema for chunk response."""

    id: str
    tenant_id: str
    workspace_id: str
    knowledge_id: str
    document_id: str
    document_version: int
    chunk_no: int
    chunk_key: str | None
    text_preview: str | None
    start_offset: int | None
    end_offset: int | None
    page_no: int | None
    section_path: list[str]
    char_count: int | None
    token_count: int | None
    index_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChunkUpdate(BaseModel):
    """Schema for updating a chunk."""

    content: str | None = None
    """Updated chunk content."""

    index_status: str | None = Field(
        default=None,
        pattern="^(pending|indexed|failed|disabled)$",
    )
    """Chunk index status."""


class IndexResponse(BaseModel):
    """Schema for index response."""

    id: str
    tenant_id: str
    workspace_id: str
    knowledge_id: str
    name: str
    is_primary: bool
    provider: str
    embedding_model_ref: str
    dimension: int
    metric_type: str
    status: str
    build_version: int
    last_build_at: datetime | None
    last_run_id: str | None
    doc_count: int
    chunk_count: int
    vector_count: int
    last_error_code: str | None
    last_error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IndexCreate(BaseModel):
    """Schema for creating an index."""

    name: str = Field(..., min_length=1, max_length=255)
    """Index name."""

    provider: str = Field(default="milvus")
    """Vector provider."""

    embedding_model_ref: str
    """Embedding model reference."""

    dimension: int = Field(default=0, ge=0)
    """Embedding dimension (0 means infer later)."""

    metric_type: str = Field(default="cosine")
    """Metric type."""

    is_primary: bool = Field(default=False)
    """Whether this is the primary index."""

    collection_name: str | None = None
    """Collection name in vector store."""

    partition_strategy: str | None = None
    """Partition strategy."""

    namespace: str | None = None
    """Namespace."""

    index_params_json: dict[str, Any] | None = Field(default_factory=dict)
    """Index params."""

    search_params_json: dict[str, Any] | None = Field(default_factory=dict)
    """Search params."""

    reranker_ref: str | None = None
    """Reranker reference."""

    filters_json: dict[str, Any] | None = Field(default_factory=dict)
    """Default filters."""


class IndexUpdate(BaseModel):
    """Schema for updating an index."""

    name: str | None = Field(None, min_length=1, max_length=255)
    """Index name."""

    is_primary: bool | None = None
    """Set as primary index."""

    status: str | None = Field(None, pattern="^(draft|building|ready|failed|disabled)$")
    """Index status."""

    search_params_json: dict[str, Any] | None = None
    """Search params."""

    reranker_ref: str | None = None
    """Reranker reference."""

    filters_json: dict[str, Any] | None = None
    """Default filters."""


class IngestTaskResponse(BaseModel):
    """Schema for ingest task response."""

    id: str
    tenant_id: str
    workspace_id: str
    knowledge_id: str
    document_id: str | None
    status: str
    payload_json: dict[str, Any]
    run_id: str | None
    error_code: str | None
    error_message: str | None
    retry_count: int
    max_retries: int
    started_at: datetime | None
    finished_at: datetime | None
    created_by: str | None
    updated_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeConsumerUsageResponse(BaseModel):
    """Schema for knowledge-linked consuming resources."""

    resource_id: str
    resource_name: str
    resource_kind: str
    resource_status: str
    resource_version_id: str
    resource_version: int
    resource_version_status: str
    resource_version_created_at: datetime
    run_count: int
    last_run_at: datetime | None
