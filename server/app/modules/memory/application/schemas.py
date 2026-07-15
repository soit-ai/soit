""" schemas

Memory domain schemas.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MemoryCreate(BaseModel):
    """Create memory request."""

    content: dict[str, Any]
    """Memory content."""

    memory_type: str = Field(default="long", pattern="^(short|long)$")
    """Memory type."""

    user_id: str | None = None
    """Optional owner user_id."""

    content_summary: str | None = Field(default=None, max_length=2048)
    """Optional summary."""

    metadata_json: dict[str, Any] | None = None
    """Optional metadata."""

    tags: list[str] | None = None
    """Tags."""


class MemoryQuery(BaseModel):
    """Memory query request."""

    query: str = Field(..., min_length=1)
    """Query text."""

    top_k: int = Field(default=5, ge=1, le=50)
    """Top results."""

    memory_type: str | None = Field(default=None, pattern="^(short|long)$")
    """Memory type filter."""

    user_id: str | None = None
    """Optional owner filter."""


class MemoryResponse(BaseModel):
    """Memory response."""

    id: str
    tenant_id: str
    workspace_id: str
    user_id: str | None
    memory_type: str
    content: dict[str, Any]
    content_summary: str | None
    metadata_json: dict[str, Any] | None
    tags: list[str] | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class MemorySearchResult(BaseModel):
    """Memory search result."""

    memory: MemoryResponse
    score: float
