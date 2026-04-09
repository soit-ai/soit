""" models

Knowledge domain DB models backed by the knowledge storage tables.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Column, JSON, Relationship
from sqlalchemy import Text

from app.kernel.commons.time import utc_now
from app.kernel.commons.ids import generate_ulid


def generate_knowledge_id() -> str:
    """Generate knowledge ID."""
    return f"knw_{generate_ulid()}"


def generate_document_id() -> str:
    """Generate document ID."""
    return f"doc_{generate_ulid()}"


def generate_chunk_id() -> str:
    """Generate chunk ID."""
    return f"chunk_{generate_ulid()}"


def generate_index_id() -> str:
    """Generate index ID."""
    return f"idx_{generate_ulid()}"


def generate_ingest_task_id() -> str:
    """Generate knowledge ingest task ID."""
    return f"ingest_{generate_ulid()}"


class Knowledge(SQLModel, table=True):
    """Knowledge model - workspace-scoped knowledge base."""
    
    __tablename__ = "knowledge"
    
    id: str = Field(primary_key=True, default_factory=generate_knowledge_id)
    """Knowledge ID."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""
    
    name: str = Field()
    """Knowledge name."""
    
    type: str = Field(default="document")
    """Knowledge type: document, qa, code, graph, other."""
    
    description: Optional[str] = Field(default=None, nullable=True)
    """Knowledge description."""
    
    status: str = Field(default="active")
    """Status: active, archived, disabled."""
    
    visibility: str = Field(default="private")
    """Visibility: private, workspace, tenant."""
    
    settings_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """General settings (parser/language/filters)."""
    
    chunking_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Default chunking strategy (size/overlap/separators)."""
    
    retrieval_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Default retrieval strategy (top_k/rerank/filters)."""
    
    default_embedding_model_ref: Optional[str] = Field(default=None, nullable=True)
    """Default embedding model reference."""
    
    default_reranker_ref: Optional[str] = Field(default=None, nullable=True)
    """Default reranker reference."""
    
    default_index_id: Optional[str] = Field(default=None, nullable=True)
    """Default index ID."""
    
    doc_count: int = Field(default=0)
    """Document count."""
    
    chunk_count: int = Field(default=0)
    """Chunk count."""
    
    last_ingested_at: Optional[datetime] = Field(default=None, nullable=True)
    """Last ingestion timestamp."""
    
    last_indexed_at: Optional[datetime] = Field(default=None, nullable=True)
    """Last indexing timestamp."""
    
    tags: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    """Tags."""
    
    created_by: Optional[str] = Field(default=None, nullable=True)
    """User ID who created."""
    
    updated_by: Optional[str] = Field(default=None, nullable=True)
    """User ID who last updated."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""
    
    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""
    
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)
    """Soft delete timestamp."""


class KnowledgeDocument(SQLModel, table=True):
    """KnowledgeDocument model - document with versioning."""
    
    __tablename__ = "knowledge_documents"
    
    id: str = Field(primary_key=True, default_factory=generate_document_id)
    """Document ID."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""
    
    knowledge_id: str = Field(foreign_key="knowledge.id", index=True)
    """Knowledge ID (foreign key)."""
    
    doc_key: str = Field()
    """Document key (stable identifier for versioning)."""
    
    version: int = Field()
    """Version number (starts from 1)."""
    
    is_latest: bool = Field(default=True)
    """Is latest version flag."""
    
    source_type: str = Field()
    """Source type: upload, crawler, api, manual."""
    
    source_uri: Optional[str] = Field(default=None, nullable=True)
    """Source URI (URL/external reference)."""
    
    external_id: Optional[str] = Field(default=None, nullable=True)
    """External system ID."""
    
    file_id: Optional[str] = Field(default=None, nullable=True)
    """Uploaded file ID."""
    
    title: Optional[str] = Field(default=None, nullable=True)
    """Document title."""
    
    language: Optional[str] = Field(default=None, nullable=True)
    """Language (ISO 639-1)."""
    
    mime_type: Optional[str] = Field(default=None, nullable=True)
    """MIME type."""
    
    filename: Optional[str] = Field(default=None, nullable=True)
    """Filename."""
    
    size_bytes: Optional[int] = Field(default=None, nullable=True)
    """File size in bytes."""
    
    checksum: Optional[str] = Field(default=None, nullable=True)
    """File checksum (SHA256)."""
    
    content_hash: Optional[str] = Field(default=None, nullable=True)
    """Content hash (for deduplication)."""
    
    status: str = Field(default="uploaded")
    """Status: uploaded, parsing, parsed, chunking, chunked, indexing, indexed, failed, deleted."""
    
    error_code: Optional[str] = Field(default=None, nullable=True)
    """Error code if failed."""
    
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    """Error message if failed."""
    
    retry_count: int = Field(default=0)
    """Retry count."""
    
    raw_text_artifact_key: Optional[str] = Field(default=None, nullable=True)
    """Raw text artifact key (object storage)."""
    
    parsed_artifact_key: Optional[str] = Field(default=None, nullable=True)
    """Parsed artifact key (structured data)."""
    
    chunking_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Chunking strategy used for this version."""
    
    parse_meta_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Parse metadata (pages, tables, images, etc.)."""
    
    index_meta_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Index metadata (vector count, errors, etc.)."""
    
    access_policy_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Access policy (departments/roles/redaction)."""
    
    created_by: Optional[str] = Field(default=None, nullable=True)
    """User ID who created."""
    
    updated_by: Optional[str] = Field(default=None, nullable=True)
    """User ID who last updated."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""
    
    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""
    
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)
    """Soft delete timestamp."""


class KnowledgeIngestTask(SQLModel, table=True):
    """Knowledge ingestion task model."""

    __tablename__ = "knowledge_ingest_tasks"

    id: str = Field(primary_key=True, default_factory=generate_ingest_task_id)
    """Task ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    knowledge_id: str = Field(foreign_key="knowledge.id", index=True)
    """Knowledge ID (foreign key)."""

    document_id: Optional[str] = Field(
        default=None,
        nullable=True,
        index=True,
    )
    """Related document ID."""

    status: str = Field(default="queued")
    """Status: queued, running, succeeded, failed, canceled."""

    payload_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Ingestion payload snapshot (DocumentUpload)."""

    run_id: Optional[str] = Field(default=None, nullable=True)
    """Run ID for tracing."""

    error_code: Optional[str] = Field(default=None, nullable=True)
    """Error code if failed."""

    error_message: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    """Error message if failed."""

    retry_count: int = Field(default=0)
    """Retry count."""

    max_retries: int = Field(default=1)
    """Max retries."""

    started_at: Optional[datetime] = Field(default=None, nullable=True)
    """Start timestamp."""

    finished_at: Optional[datetime] = Field(default=None, nullable=True)
    """Finish timestamp."""

    created_by: Optional[str] = Field(default=None, nullable=True)
    """User ID who created."""

    updated_by: Optional[str] = Field(default=None, nullable=True)
    """User ID who last updated."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class KnowledgeChunk(SQLModel, table=True):
    """KnowledgeChunk model - document chunk."""
    
    __tablename__ = "knowledge_chunks"
    
    id: str = Field(primary_key=True, default_factory=generate_chunk_id)
    """Chunk ID."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""
    
    knowledge_id: str = Field(index=True)
    """Knowledge ID (redundant for query performance)."""
    
    document_id: str = Field(foreign_key="knowledge_documents.id", index=True)
    """Document ID (foreign key)."""
    
    document_version: int = Field()
    """Document version (redundant for traceability)."""
    
    chunk_no: int = Field()
    """Chunk number (0-indexed)."""
    
    chunk_key: Optional[str] = Field(default=None, nullable=True)
    """Stable chunk key (e.g., {doc_key}:{version}:{chunk_no})."""
    
    content_hash: Optional[str] = Field(default=None, nullable=True)
    """Content hash."""
    
    text_preview: Optional[str] = Field(default=None, nullable=True, max_length=2048)
    """Text preview (<= 512 chars)."""
    
    text_artifact_key: Optional[str] = Field(default=None, nullable=True)
    """Full text artifact key (object storage)."""
    
    start_offset: Optional[int] = Field(default=None, nullable=True)
    """Start character offset."""
    
    end_offset: Optional[int] = Field(default=None, nullable=True)
    """End character offset."""
    
    page_no: Optional[int] = Field(default=None, nullable=True)
    """Page number."""
    
    section_path: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    """Section path (e.g., ["H1", "H2"])."""
    
    bbox_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Bounding box (PDF coordinates)."""
    
    source_meta_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Source metadata (table/code/image references)."""
    
    char_count: Optional[int] = Field(default=None, nullable=True)
    """Character count."""
    
    token_count: Optional[int] = Field(default=None, nullable=True)
    """Token count."""
    
    embedding_model_ref: Optional[str] = Field(default=None, nullable=True)
    """Embedding model reference used."""
    
    vector_ref: Optional[str] = Field(default=None, nullable=True)
    """Vector database reference (primary key)."""
    
    indexed_at: Optional[datetime] = Field(default=None, nullable=True)
    """Indexing timestamp."""
    
    index_status: str = Field(default="pending")
    """Index status: pending, indexed, failed."""
    
    index_error: Optional[str] = Field(default=None, nullable=True)
    """Index error message."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""
    
    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class KnowledgeIndex(SQLModel, table=True):
    """KnowledgeIndex model - vector index configuration."""
    
    __tablename__ = "knowledge_indexes"
    
    id: str = Field(primary_key=True, default_factory=generate_index_id)
    """Index ID."""
    
    tenant_id: str = Field(index=True)
    """Tenant ID."""
    
    workspace_id: str = Field(index=True)
    """Workspace ID."""
    
    knowledge_id: str = Field(foreign_key="knowledge.id", index=True)
    """Knowledge ID (foreign key)."""
    
    name: str = Field()
    """Index name."""
    
    is_primary: bool = Field(default=False)
    """Is primary index flag."""
    
    provider: str = Field()
    """Provider: milvus, pgvector, elastic, other."""
    
    endpoint_ref: Optional[str] = Field(default=None, nullable=True)
    """Endpoint reference (gateway config)."""
    
    collection_name: Optional[str] = Field(default=None, nullable=True)
    """Collection name."""
    
    partition_strategy: Optional[str] = Field(default=None, nullable=True)
    """Partition strategy: tenant, workspace, knowledge, none."""
    
    namespace: Optional[str] = Field(default=None, nullable=True)
    """Namespace for logical isolation."""
    
    embedding_model_ref: str = Field()
    """Embedding model reference."""
    
    dimension: int = Field()
    """Vector dimension."""
    
    metric_type: str = Field()
    """Metric type: cosine, ip, l2."""
    
    index_params_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Index building parameters."""
    
    search_params_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Search parameters (ef/top_k)."""
    
    reranker_ref: Optional[str] = Field(default=None, nullable=True)
    """Reranker reference."""
    
    filters_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Default filter strategy."""
    
    status: str = Field(default="draft")
    """Status: draft, building, ready, failed, disabled."""
    
    build_version: int = Field(default=1)
    """Build version (increments on rebuild)."""
    
    last_build_at: Optional[datetime] = Field(default=None, nullable=True)
    """Last build timestamp."""
    
    doc_count: int = Field(default=0)
    """Document count in index."""
    
    chunk_count: int = Field(default=0)
    """Chunk count in index."""
    
    vector_count: int = Field(default=0)
    """Vector count in index."""
    
    last_error_code: Optional[str] = Field(default=None, nullable=True)
    """Last error code."""
    
    last_error_message: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    """Last error message."""
    
    created_by: Optional[str] = Field(default=None, nullable=True)
    """User ID who created."""
    
    updated_by: Optional[str] = Field(default=None, nullable=True)
    """User ID who last updated."""
    
    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""
    
    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""
    
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)
    """Soft delete timestamp."""
