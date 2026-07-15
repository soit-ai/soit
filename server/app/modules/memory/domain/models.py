""" models

Memory domain DB models.
"""

from datetime import datetime
from typing import Any

from sqlmodel import JSON, Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


def generate_memory_id() -> str:
    """Generate memory ID."""
    return f"mem_{generate_ulid()}"


class MemoryItem(SQLModel, table=True):
    """Memory item stored per tenant/workspace."""

    __tablename__ = "memories"

    id: str = Field(primary_key=True, default_factory=generate_memory_id)
    """Memory ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    user_id: str | None = Field(default=None, nullable=True, index=True)
    """User ID who owns this memory."""

    memory_type: str = Field(default="long", index=True)
    """Memory type: short, long."""

    content: dict[str, Any] = Field(sa_column=Column(JSON))
    """Raw memory content."""

    content_summary: str | None = Field(default=None, nullable=True)
    """Short summary for quick display."""

    vector_ref: str | None = Field(default=None, nullable=True)
    """Vector reference ID in vector store."""

    metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Metadata for memory."""

    tags: list[str] | None = Field(default=None, sa_column=Column(JSON))
    """Tags."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""

    deleted_at: datetime | None = Field(default=None, nullable=True)
    """Soft delete timestamp."""
