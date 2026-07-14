"""Observe/idempotency persistence models."""

from datetime import datetime
from typing import Any

from sqlalchemy import UniqueConstraint
from sqlmodel import JSON, Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


class IdempotencyKey(SQLModel, table=True):
    """Idempotency key record."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "user_id",
            "scope",
            "key",
            name="ux_idempotency_key_scope",
        ),
    )

    id: str = Field(primary_key=True, default_factory=generate_ulid)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    user_id: str | None = Field(default=None, index=True)
    scope: str = Field(index=True)
    key: str = Field(index=True)
    request_hash: str
    status: str = Field(default="in_progress")
    response_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
