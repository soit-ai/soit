""" schemas

Dataset domain Pydantic schemas.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


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
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
    """Chunk metadata."""


class QueryResponse(BaseModel):
    """Schema for query response."""
    
    results: List[QueryResult]
    """Query results."""
    
    total: int
    """Total results count."""


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
    
    class Config:
        from_attributes = True


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
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


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
    
    class Config:
        from_attributes = True
