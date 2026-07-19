"""Persistent product feedback records."""

from datetime import datetime
from typing import Any

from sqlalchemy import Index, Text
from sqlmodel import JSON, Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


class ProductFeedback(SQLModel, table=True):
    """Workspace-local product issue or feature request."""

    __tablename__ = "product_feedbacks"
    __table_args__ = (
        Index(
            "ix_product_feedbacks_scope_created",
            "tenant_id",
            "workspace_id",
            "created_at",
        ),
        Index(
            "ix_product_feedbacks_scope_creator",
            "tenant_id",
            "workspace_id",
            "created_by",
        ),
        Index(
            "ix_product_feedbacks_scope_status_priority",
            "tenant_id",
            "workspace_id",
            "status",
            "priority",
        ),
    )

    id: str = Field(
        primary_key=True,
        default_factory=lambda: f"fbk_{generate_ulid()}",
        max_length=64,
    )
    tenant_id: str = Field(index=True, max_length=64)
    workspace_id: str = Field(index=True, max_length=64)
    title: str = Field(max_length=200)
    description: str = Field(sa_column=Column(Text, nullable=False))
    category: str = Field(default="other", index=True, max_length=32)
    priority: str = Field(default="medium", index=True, max_length=32)
    status: str = Field(default="open", index=True, max_length=32)
    context_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    created_by: str = Field(index=True, max_length=64)
    updated_by: str = Field(max_length=64)
    resolved_by: str | None = Field(default=None, max_length=64)
    resolution_note: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    resolved_at: datetime | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
