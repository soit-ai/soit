""" idempotency

Idempotency key records for write endpoints.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import UniqueConstraint, select, and_
from sqlalchemy.orm import Session

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext


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
    user_id: Optional[str] = Field(default=None, index=True)
    scope: str = Field(index=True)
    key: str = Field(index=True)
    request_hash: str
    status: str = Field(default="in_progress")
    response_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class IdempotencyRepository:
    """Repository for idempotency keys."""

    def __init__(self, db: Session, ctx: RequestContext):
        self.db = db
        self.ctx = ctx

    def get(self, scope: str, key: str) -> Optional[IdempotencyKey]:
        query = select(IdempotencyKey).where(
            and_(
                IdempotencyKey.tenant_id == self.ctx.tenant_id,
                IdempotencyKey.workspace_id == self.ctx.workspace_id,
                IdempotencyKey.user_id == self.ctx.user_id,
                IdempotencyKey.scope == scope,
                IdempotencyKey.key == key,
            )
        )
        result = self.db.exec(query).first()
        if result and not hasattr(result, "request_hash"):
            try:
                return result[0]
            except Exception:
                return None
        return result

    def create_in_progress(
        self,
        scope: str,
        key: str,
        request_hash: str,
    ) -> IdempotencyKey:
        record = IdempotencyKey(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            user_id=self.ctx.user_id,
            scope=scope,
            key=key,
            request_hash=request_hash,
            status="in_progress",
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def update_response(
        self,
        record: IdempotencyKey,
        response_json: Dict[str, Any],
        status: str = "completed",
    ) -> IdempotencyKey:
        record.status = status
        record.response_json = response_json
        record.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(record)
        return record

    def mark_in_progress(
        self,
        record: IdempotencyKey,
    ) -> IdempotencyKey:
        record.status = "in_progress"
        record.response_json = None
        record.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(record)
        return record

    def mark_failed(
        self,
        record: IdempotencyKey,
    ) -> IdempotencyKey:
        record.status = "failed"
        record.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(record)
        return record
