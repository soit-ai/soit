""" schemas

Memory domain schemas.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class MemoryCreate(BaseModel):
    """Create memory request."""

    content: Dict[str, Any]
    """Memory content."""

    memory_type: str = Field(default="long", pattern="^(short|long)$")
    """Memory type."""

    user_id: Optional[str] = None
    """Optional owner user_id."""

    content_summary: Optional[str] = Field(default=None, max_length=2048)
    """Optional summary."""

    metadata_json: Optional[Dict[str, Any]] = None
    """Optional metadata."""

    tags: Optional[List[str]] = None
    """Tags."""


class MemoryQuery(BaseModel):
    """Memory query request."""

    query: str = Field(..., min_length=1)
    """Query text."""

    top_k: int = Field(default=5, ge=1, le=50)
    """Top results."""

    memory_type: Optional[str] = Field(default=None, pattern="^(short|long)$")
    """Memory type filter."""

    user_id: Optional[str] = None
    """Optional owner filter."""


class MemoryResponse(BaseModel):
    """Memory response."""

    id: str
    tenant_id: str
    workspace_id: str
    user_id: Optional[str]
    memory_type: str
    content: Dict[str, Any]
    content_summary: Optional[str]
    metadata_json: Optional[Dict[str, Any]]
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class MemorySearchResult(BaseModel):
    """Memory search result."""

    memory: MemoryResponse
    score: float
