"""Persistence model for governed conversation attachments."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index
from sqlmodel import Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


def generate_attachment_id() -> str:
    return f"att_{generate_ulid()}"


class Attachment(SQLModel, table=True):
    """Tenant/workspace-scoped object uploaded for a conversation turn."""

    __tablename__ = "attachments"
    __table_args__ = (
        Index("ix_attachments_scope_created", "tenant_id", "workspace_id", "created_at"),
        Index("ix_attachments_thread_created", "thread_id", "created_at"),
        Index("ix_attachments_checksum", "checksum"),
    )

    id: str = Field(primary_key=True, default_factory=generate_attachment_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    thread_id: str | None = Field(default=None, index=True)
    filename: str
    content_type: str = Field(index=True)
    size_bytes: int
    checksum: str
    storage_key: str
    status: str = Field(default="uploading", index=True)
    created_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
