""" models

Knowledge domain DB models backed by the knowledge storage tables.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Index, Text, text
from sqlmodel import JSON, Column, Field, SQLModel
from sqlmodel.sql.sqltypes import UTCDateTime

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


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


def generate_source_id() -> str:
    """Generate knowledge source ID."""
    return f"ksrc_{generate_ulid()}"


def generate_source_item_id() -> str:
    """Generate knowledge source item ID."""
    return f"ksi_{generate_ulid()}"


def generate_sync_run_id() -> str:
    """Generate knowledge sync run ID."""
    return f"ksync_{generate_ulid()}"


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

    description: str | None = Field(default=None, nullable=True)
    """Knowledge description."""

    status: str = Field(default="active")
    """Status: active, archived, disabled."""

    visibility: str = Field(default="workspace")
    """Visibility: private (creator, owners, admins, grantees), workspace, tenant."""

    settings_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """General settings (parser/language/filters)."""

    chunking_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Default chunking strategy (size/overlap/separators)."""

    retrieval_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Default retrieval strategy (top_k/rerank/filters)."""

    default_embedding_model_ref: str | None = Field(default=None, nullable=True)
    """Default embedding model reference."""

    default_reranker_ref: str | None = Field(default=None, nullable=True)
    """Default reranker reference."""

    default_index_id: str | None = Field(default=None, nullable=True)
    """Default index ID."""

    doc_count: int = Field(default=0)
    """Document count."""

    chunk_count: int = Field(default=0)
    """Chunk count."""

    last_ingested_at: datetime | None = Field(default=None, nullable=True)
    """Last ingestion timestamp."""

    last_indexed_at: datetime | None = Field(default=None, nullable=True)
    """Last indexing timestamp."""

    tags: list[str] | None = Field(default=None, sa_column=Column(JSON))
    """Tags."""

    created_by: str | None = Field(default=None, nullable=True)
    """User ID who created."""

    updated_by: str | None = Field(default=None, nullable=True)
    """User ID who last updated."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""

    deleted_at: datetime | None = Field(default=None, nullable=True)
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

    knowledge_id: str = Field(index=True)
    """Knowledge ID (foreign key)."""

    doc_key: str = Field()
    """Document key (stable identifier for versioning)."""

    version: int = Field()
    """Version number (starts from 1)."""

    is_latest: bool = Field(default=True)
    """Is latest version flag."""

    source_kind: str = Field()
    """Source kind: upload, crawler, api, manual."""

    source_uri: str | None = Field(default=None, nullable=True)
    """Source URI (URL/external reference)."""

    external_id: str | None = Field(default=None, nullable=True)
    """External system ID."""

    file_id: str | None = Field(default=None, nullable=True)
    """Uploaded file ID."""

    title: str | None = Field(default=None, nullable=True)
    """Document title."""

    language: str | None = Field(default=None, nullable=True)
    """Language (ISO 639-1)."""

    mime_type: str | None = Field(default=None, nullable=True)
    """MIME type."""

    filename: str | None = Field(default=None, nullable=True)
    """Filename."""

    size_bytes: int | None = Field(default=None, nullable=True)
    """File size in bytes."""

    checksum: str | None = Field(default=None, nullable=True)
    """File checksum (SHA256)."""

    content_hash: str | None = Field(default=None, nullable=True)
    """Content hash (for deduplication)."""

    status: str = Field(default="uploaded")
    """Status: uploaded, parsing, parsed, chunking, chunked, indexing, indexed, failed, deleted."""

    error_code: str | None = Field(default=None, nullable=True)
    """Error code if failed."""

    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    """Error message if failed."""

    retry_count: int = Field(default=0)
    """Retry count."""

    raw_text_artifact_key: str | None = Field(default=None, nullable=True)
    """Raw text artifact key (object storage)."""

    parsed_artifact_key: str | None = Field(default=None, nullable=True)
    """Parsed artifact key (structured data)."""

    chunking_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Chunking strategy used for this version."""

    parse_meta_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Parse metadata (pages, tables, images, etc.)."""

    index_meta_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Index metadata (vector count, errors, etc.)."""

    access_policy_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Access policy (departments/roles/redaction)."""

    created_by: str | None = Field(default=None, nullable=True)
    """User ID who created."""

    updated_by: str | None = Field(default=None, nullable=True)
    """User ID who last updated."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""

    deleted_at: datetime | None = Field(default=None, nullable=True)
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

    knowledge_id: str = Field(index=True)
    """Knowledge ID (foreign key)."""

    document_id: str | None = Field(
        default=None,
        nullable=True,
        index=True,
    )
    """Related document ID."""

    status: str = Field(default="queued", index=True)
    """Status: queued, running, succeeded, failed, canceled."""

    lease_owner: str | None = Field(default=None, nullable=True, index=True)
    """Worker currently holding the execution lease."""

    lease_expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(UTCDateTime(), nullable=True, index=True),
    )
    """Lease expiry; a running task past this moment is reclaimable."""

    attempt_count: int = Field(default=0)
    """Number of times this task has been claimed for execution."""

    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Ingestion payload snapshot (DocumentUpload)."""

    run_id: str | None = Field(default=None, nullable=True)
    """Run ID for tracing."""

    error_code: str | None = Field(default=None, nullable=True)
    """Error code if failed."""

    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    """Error message if failed."""

    retry_count: int = Field(default=0)
    """Retry count."""

    max_retries: int = Field(default=1)
    """Max retries."""

    started_at: datetime | None = Field(default=None, nullable=True)
    """Start timestamp."""

    finished_at: datetime | None = Field(default=None, nullable=True)
    """Finish timestamp."""

    created_by: str | None = Field(default=None, nullable=True)
    """User ID who created."""

    updated_by: str | None = Field(default=None, nullable=True)
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

    document_id: str = Field(index=True)
    """Document ID (foreign key)."""

    document_version: int = Field()
    """Document version (redundant for traceability)."""

    chunk_no: int = Field()
    """Chunk number (0-indexed)."""

    chunk_key: str | None = Field(default=None, nullable=True)
    """Stable chunk key (e.g., {doc_key}:{version}:{chunk_no})."""

    content_hash: str | None = Field(default=None, nullable=True)
    """Content hash."""

    text_preview: str | None = Field(default=None, nullable=True, max_length=2048)
    """Text preview (<= 512 chars)."""

    text_artifact_key: str | None = Field(default=None, nullable=True)
    """Full text artifact key (object storage)."""

    start_offset: int | None = Field(default=None, nullable=True)
    """Start character offset."""

    end_offset: int | None = Field(default=None, nullable=True)
    """End character offset."""

    page_no: int | None = Field(default=None, nullable=True)
    """Page number."""

    section_path: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    """Section path (e.g., ["H1", "H2"])."""

    bbox_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Bounding box (PDF coordinates)."""

    source_meta_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Source metadata (table/code/image references)."""

    char_count: int | None = Field(default=None, nullable=True)
    """Character count."""

    token_count: int | None = Field(default=None, nullable=True)
    """Token count."""

    embedding_model_ref: str | None = Field(default=None, nullable=True)
    """Embedding model reference used."""

    vector_ref: str | None = Field(default=None, nullable=True)
    """Vector database reference (primary key)."""

    indexed_at: datetime | None = Field(default=None, nullable=True)
    """Indexing timestamp."""

    index_status: str = Field(default="pending")
    """Index status: pending, indexed, failed."""

    index_error: str | None = Field(default=None, nullable=True)
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

    knowledge_id: str = Field(index=True)
    """Knowledge ID (foreign key)."""

    name: str = Field()
    """Index name."""

    is_primary: bool = Field(default=False)
    """Is primary index flag."""

    provider: str = Field()
    """Provider: milvus, pgvector, elastic, other."""

    endpoint_ref: str | None = Field(default=None, nullable=True)
    """Endpoint reference (gateway config)."""

    collection_name: str | None = Field(default=None, nullable=True)
    """Collection name."""

    partition_strategy: str | None = Field(default=None, nullable=True)
    """Partition strategy: tenant, workspace, knowledge, none."""

    namespace: str | None = Field(default=None, nullable=True)
    """Namespace for logical isolation."""

    embedding_model_ref: str = Field()
    """Embedding model reference."""

    dimension: int = Field()
    """Vector dimension."""

    metric_type: str = Field()
    """Metric type: cosine, ip, l2."""

    index_params_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Index building parameters."""

    search_params_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Search parameters (ef/top_k)."""

    reranker_ref: str | None = Field(default=None, nullable=True)
    """Reranker reference."""

    filters_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Default filter strategy."""

    status: str = Field(default="draft")
    """Status: draft, building, ready, failed, disabled."""

    build_version: int = Field(default=1)
    """Build version (increments on rebuild)."""

    last_build_at: datetime | None = Field(default=None, nullable=True)
    """Last build timestamp."""

    last_run_id: str | None = Field(default=None, nullable=True)
    """Last observable run ID."""

    doc_count: int = Field(default=0)
    """Document count in index."""

    chunk_count: int = Field(default=0)
    """Chunk count in index."""

    vector_count: int = Field(default=0)
    """Vector count in index."""

    last_error_code: str | None = Field(default=None, nullable=True)
    """Last error code."""

    last_error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    """Last error message."""

    created_by: str | None = Field(default=None, nullable=True)
    """User ID who created."""

    updated_by: str | None = Field(default=None, nullable=True)
    """User ID who last updated."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""

    deleted_at: datetime | None = Field(default=None, nullable=True)
    """Soft delete timestamp."""


class KnowledgeSource(SQLModel, table=True):
    """KnowledgeSource model - an external system a knowledge base is synced from."""

    __tablename__ = "knowledge_sources"

    id: str = Field(primary_key=True, default_factory=generate_source_id)
    """Source ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    knowledge_id: str = Field(index=True)
    """Knowledge ID the source feeds (reference enforced in code)."""

    name: str = Field()
    """Source display name."""

    connector_kind: str = Field()
    """Connector kind: s3, web."""

    config_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Connector configuration. Never holds credentials."""

    secret_id: str | None = Field(default=None, nullable=True)
    """Opaque secret id the connector's credentials are resolved from."""

    limits_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Per-run caps: max_items, max_item_bytes, max_total_bytes."""

    schedule_cron: str | None = Field(default=None, nullable=True)
    """Five-field cron expression; empty means manual sync only."""

    schedule_timezone: str = Field(default="UTC")
    """IANA time zone the cron expression is evaluated in."""

    enabled: bool = Field(default=True)
    """Disabled sources are neither scheduled nor synced on demand."""

    delete_removed: bool = Field(default=False)
    """Delete a document once its item disappears from the remote."""

    next_sync_at: datetime | None = Field(
        default=None,
        sa_column=Column(UTCDateTime(), nullable=True, index=True),
    )
    """When the schedule next fires."""

    last_sync_at: datetime | None = Field(default=None, nullable=True)
    """When the most recent run finished."""

    last_status: str | None = Field(default=None, nullable=True)
    """Status of the most recent run."""

    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    """Error of the most recent run, if it failed."""

    last_counts_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Counts of the most recent finished run."""

    created_by: str | None = Field(default=None, nullable=True)
    """User ID who created."""

    updated_by: str | None = Field(default=None, nullable=True)
    """User ID who last updated."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""

    deleted_at: datetime | None = Field(default=None, nullable=True)
    """Soft delete timestamp."""


class KnowledgeSourceItem(SQLModel, table=True):
    """KnowledgeSourceItem model - what a source last saw of one remote item."""

    __tablename__ = "knowledge_source_items"
    __table_args__ = (
        Index("uq_knowledge_source_items_source_external", "source_id", "external_id", unique=True),
    )

    id: str = Field(primary_key=True, default_factory=generate_source_item_id)
    """Item ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    source_id: str = Field(index=True)
    """Source ID (reference enforced in code)."""

    external_id: str = Field()
    """The remote identity of the item (object key, normalized URL)."""

    doc_key: str | None = Field(default=None, nullable=True)
    """Document key the item's versions are stored under."""

    document_id: str | None = Field(default=None, nullable=True)
    """Latest document ingested for the item."""

    remote_etag: str | None = Field(default=None, nullable=True)
    """Remote ETag at the last successful sync."""

    remote_modified: str | None = Field(default=None, nullable=True)
    """Remote modification marker at the last successful sync."""

    remote_size: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    """Remote size in bytes at the last successful sync."""

    content_hash: str | None = Field(default=None, nullable=True)
    """SHA-256 of the content last ingested."""

    status: str = Field(default="present")
    """Status: present, removed, failed."""

    meta_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    """Connector-private per-item state."""

    last_seen_at: datetime | None = Field(default=None, nullable=True)
    """Last time a run saw the item in the remote."""

    last_synced_at: datetime | None = Field(default=None, nullable=True)
    """Last time the item's content was ingested."""

    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    """Error of the last attempt, if it failed."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class KnowledgeSyncRun(SQLModel, table=True):
    """KnowledgeSyncRun model - one execution of a source's sync."""

    __tablename__ = "knowledge_sync_runs"
    __table_args__ = (
        # At most one queued or running run per source, enforced by the store
        # so two schedulers or a double click cannot both start one.
        Index(
            "uq_knowledge_sync_runs_active_source",
            "source_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
            sqlite_where=text("status IN ('queued', 'running')"),
        ),
    )

    id: str = Field(primary_key=True, default_factory=generate_sync_run_id)
    """Run ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    knowledge_id: str = Field(index=True)
    """Knowledge ID."""

    source_id: str = Field(index=True)
    """Source ID (reference enforced in code)."""

    trigger: str = Field(default="manual")
    """Trigger: manual, schedule."""

    status: str = Field(default="queued", index=True)
    """Status: queued, running, succeeded, partial, failed, canceled."""

    added_count: int = Field(default=0)
    """Items ingested for the first time."""

    updated_count: int = Field(default=0)
    """Items ingested as a new version."""

    unchanged_count: int = Field(default=0)
    """Items found unchanged."""

    removed_count: int = Field(default=0)
    """Items that disappeared from the remote."""

    failed_count: int = Field(default=0)
    """Items that could not be synced."""

    skipped_count: int = Field(default=0)
    """Remote objects left out, such as unsupported file types."""

    truncated: bool = Field(default=False)
    """A cap ended the listing early, so removals were not evaluated."""

    outcomes_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    """Per-item outcomes other than unchanged, capped."""

    error_code: str | None = Field(default=None, nullable=True)
    """Error code if the run failed."""

    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    """Error message if the run failed."""

    cancel_requested: bool = Field(default=False)
    """Set to ask a running run to stop between items."""

    lease_owner: str | None = Field(default=None, nullable=True, index=True)
    """Worker currently holding the execution lease."""

    lease_expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(UTCDateTime(), nullable=True, index=True),
    )
    """Lease expiry; a running run past this moment is reclaimable."""

    attempt_count: int = Field(default=0)
    """Number of times this run has been claimed for execution."""

    requested_by: str | None = Field(default=None, nullable=True)
    """User ID who started the run, or null for a scheduled one."""

    started_at: datetime | None = Field(default=None, nullable=True)
    """Start timestamp."""

    finished_at: datetime | None = Field(default=None, nullable=True)
    """Finish timestamp."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


def generate_document_restriction_id() -> str:
    return f"kdr_{generate_ulid()}"


class KnowledgeDocumentRestriction(SQLModel, table=True):
    """A document of a knowledge base that only some readers of the base may read.

    Keyed by the document's ``doc_key``, so it holds for every version. Its
    readers are the workspace's Owners and Admins, the base's creator, and
    holders of a ``knowledge_document`` grant with ``read``.
    """

    __tablename__ = "knowledge_document_restrictions"
    __table_args__ = (
        Index(
            "uq_knowledge_document_restrictions_doc",
            "tenant_id",
            "workspace_id",
            "knowledge_id",
            "doc_key",
            unique=True,
        ),
    )

    id: str = Field(primary_key=True, default_factory=generate_document_restriction_id)
    """Restriction ID."""

    tenant_id: str = Field()
    """Tenant ID."""

    workspace_id: str = Field()
    """Workspace ID."""

    knowledge_id: str = Field(index=True)
    """Knowledge base ID (reference enforced in code)."""

    doc_key: str = Field()
    """Key of the restricted document, all of its versions."""

    created_by: str | None = Field(default=None, nullable=True)
    """Who restricted it."""

    created_at: datetime = Field(default_factory=utc_now)
    """When it was restricted."""
