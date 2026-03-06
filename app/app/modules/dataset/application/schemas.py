""" schemas

Dataset domain Pydantic schemas.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class DatasetCreate(BaseModel):
    """Schema for creating a dataset."""
    
    name: str = Field(..., min_length=1, max_length=255)
    """Dataset name."""
    
    type: str = Field(..., pattern="^(document|qa|code|graph|other)$")
    """Dataset type."""
    
    description: Optional[str] = Field(None, max_length=1000)
    """Dataset description."""
    
    visibility: str = Field(default="private", pattern="^(private|workspace|tenant)$")
    """Visibility."""
    
    settings_json: Optional[Dict[str, Any]] = Field(default_factory=dict)
    """General settings."""
    
    chunking_json: Optional[Dict[str, Any]] = Field(default_factory=dict)
    """Chunking strategy."""
    
    retrieval_json: Optional[Dict[str, Any]] = Field(default_factory=dict)
    """Retrieval strategy."""
    
    default_embedding_model_ref: Optional[str] = Field(None)
    """Default embedding model."""
    
    default_reranker_ref: Optional[str] = Field(None)
    """Default reranker."""
    
    tags: Optional[List[str]] = Field(None)
    """Tags."""


class DatasetUpdate(BaseModel):
    """Schema for updating a dataset."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    """Dataset name."""
    
    description: Optional[str] = Field(None, max_length=1000)
    """Dataset description."""
    
    status: Optional[str] = Field(None, pattern="^(active|archived|disabled)$")
    """Status."""
    
    visibility: Optional[str] = Field(None, pattern="^(private|workspace|tenant)$")
    """Visibility."""
    
    settings_json: Optional[Dict[str, Any]] = None
    """General settings."""
    
    chunking_json: Optional[Dict[str, Any]] = None
    """Chunking strategy."""
    
    retrieval_json: Optional[Dict[str, Any]] = None
    """Retrieval strategy."""
    
    default_embedding_model_ref: Optional[str] = None
    """Default embedding model."""
    
    default_reranker_ref: Optional[str] = None
    """Default reranker."""
    
    tags: Optional[List[str]] = None
    """Tags."""


class DocumentUpload(BaseModel):
    """Schema for uploading a document."""
    
    doc_key: str = Field(..., min_length=1)
    """Document key."""
    
    source_type: str = Field(..., pattern="^(upload|crawler|api|manual)$")
    """Source type."""
    
    source_uri: Optional[str] = None
    """Source URI."""
    
    file_id: Optional[str] = None
    """File ID."""

    filename: Optional[str] = None
    """Original filename."""

    mime_type: Optional[str] = None
    """MIME type."""

    size_bytes: Optional[int] = None
    """File size in bytes."""

    checksum: Optional[str] = None
    """File checksum (sha256)."""

    content_hash: Optional[str] = None
    """Content hash (sha256)."""

    title: Optional[str] = None
    """Title."""
    
    language: Optional[str] = None
    """Language."""
    
    access_policy_json: Optional[Dict[str, Any]] = Field(default_factory=dict)
    """Access policy."""


class QueryRequest(BaseModel):
    """Schema for querying dataset."""
    
    query: str = Field(..., min_length=1)
    """Query text."""
    
    top_k: int = Field(default=10, ge=1, le=100)
    """Number of results."""
    
    index_id: Optional[str] = None
    """Index ID (use default if not specified)."""
    
    filter: Optional[Dict[str, Any]] = None
    """Metadata filter."""
    
    use_rerank: bool = Field(default=False)
    """Use reranking."""
    
    reranker_ref: Optional[str] = None
    """Reranker reference."""

    strategy: Optional[str] = Field(default=None, pattern="^(vector|multi_index|keyword|hybrid)$")
    """Retrieval strategy."""

    index_ids: Optional[List[str]] = None
    """Index IDs for multi-index retrieval."""

    keyword_top_k: Optional[int] = Field(default=None, ge=1, le=200)
    """Top K for keyword retrieval."""

    keyword_candidate_limit: Optional[int] = Field(default=None, ge=10, le=10000)
    """Max chunks to scan for keyword retrieval."""

    keyword_min_score: Optional[int] = Field(default=None, ge=1)
    """Minimum keyword score to include a chunk."""

    hybrid_alpha: Optional[float] = Field(default=None, ge=0.0, le=1.0)
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

    snippets: List[str] = Field(default_factory=list)
    """Snippet list for citations."""
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
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

    dataset_id: Optional[str] = None
    """Dataset ID."""

    doc_key: Optional[str] = None
    """Document key."""

    title: Optional[str] = None
    """Document title."""

    source_uri: Optional[str] = None
    """Source URI."""

    chunk_no: Optional[int] = None
    """Chunk number."""

    page_no: Optional[int] = None
    """Page number."""

    section_path: Optional[List[str]] = None
    """Section path."""

    snippet: Optional[str] = None
    """Primary snippet."""


class QueryResponse(BaseModel):
    """Schema for query response."""
    
    results: List[QueryResult]
    """Query results."""
    
    total: int
    """Total results count."""

    citations: List[QueryCitation] = Field(default_factory=list)
    """Citation list (sources + snippets)."""


class DatasetResponse(BaseModel):
    """Schema for dataset response."""
    
    id: str
    tenant_id: str
    workspace_id: str
    name: str
    type: str
    description: Optional[str]
    status: str
    visibility: str
    settings_json: Dict[str, Any]
    chunking_json: Dict[str, Any]
    retrieval_json: Dict[str, Any]
    default_embedding_model_ref: Optional[str]
    default_reranker_ref: Optional[str]
    default_index_id: Optional[str]
    doc_count: int
    chunk_count: int
    last_ingested_at: Optional[datetime]
    last_indexed_at: Optional[datetime]
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    """Schema for document response."""
    
    id: str
    tenant_id: str
    workspace_id: str
    dataset_id: str
    doc_key: str
    version: int
    is_latest: bool
    source_type: str
    title: Optional[str]
    language: Optional[str]
    mime_type: Optional[str]
    filename: Optional[str]
    size_bytes: Optional[int]
    checksum: Optional[str]
    content_hash: Optional[str]
    source_uri: Optional[str]
    file_id: Optional[str]
    error_code: Optional[str]
    error_message: Optional[str]
    retry_count: int
    status: str
    parse_meta_json: Dict[str, Any] = Field(default_factory=dict)
    index_meta_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class ChunkResponse(BaseModel):
    """Schema for chunk response."""

    id: str
    tenant_id: str
    workspace_id: str
    dataset_id: str
    document_id: str
    document_version: int
    chunk_no: int
    chunk_key: Optional[str]
    text_preview: Optional[str]
    start_offset: Optional[int]
    end_offset: Optional[int]
    page_no: Optional[int]
    section_path: List[str]
    char_count: Optional[int]
    token_count: Optional[int]
    index_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChunkUpdate(BaseModel):
    """Schema for updating a chunk."""

    content: Optional[str] = None
    """Updated chunk content."""

    index_status: Optional[str] = Field(
        default=None,
        pattern="^(pending|indexed|failed|disabled)$",
    )
    """Chunk index status."""


class IndexResponse(BaseModel):
    """Schema for index response."""
    
    id: str
    tenant_id: str
    workspace_id: str
    dataset_id: str
    name: str
    is_primary: bool
    provider: str
    embedding_model_ref: str
    dimension: int
    metric_type: str
    status: str
    build_version: int
    doc_count: int
    chunk_count: int
    vector_count: int
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

    collection_name: Optional[str] = None
    """Collection name in vector store."""

    partition_strategy: Optional[str] = None
    """Partition strategy."""

    namespace: Optional[str] = None
    """Namespace."""

    index_params_json: Optional[Dict[str, Any]] = Field(default_factory=dict)
    """Index params."""

    search_params_json: Optional[Dict[str, Any]] = Field(default_factory=dict)
    """Search params."""

    reranker_ref: Optional[str] = None
    """Reranker reference."""

    filters_json: Optional[Dict[str, Any]] = Field(default_factory=dict)
    """Default filters."""


class IndexUpdate(BaseModel):
    """Schema for updating an index."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    """Index name."""

    is_primary: Optional[bool] = None
    """Set as primary index."""

    status: Optional[str] = Field(None, pattern="^(draft|building|ready|failed|disabled)$")
    """Index status."""

    search_params_json: Optional[Dict[str, Any]] = None
    """Search params."""

    reranker_ref: Optional[str] = None
    """Reranker reference."""

    filters_json: Optional[Dict[str, Any]] = None
    """Default filters."""


class IngestTaskResponse(BaseModel):
    """Schema for ingest task response."""

    id: str
    tenant_id: str
    workspace_id: str
    dataset_id: str
    document_id: Optional[str]
    status: str
    payload_json: Dict[str, Any]
    run_id: Optional[str]
    error_code: Optional[str]
    error_message: Optional[str]
    retry_count: int
    max_retries: int
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetApplicationUsageResponse(BaseModel):
    """Schema for dataset-linked application versions."""

    app_id: str
    app_name: str
    app_type: str
    app_status: str
    app_version_id: str
    app_version: int
    app_version_status: str
    app_version_created_at: datetime
    run_count: int
    last_run_at: Optional[datetime]
