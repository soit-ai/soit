"""Idempotency repository for write endpoints."""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.observe import IdempotencyKey


class IdempotencyRepository:
    """Repository for idempotency keys."""

    def __init__(self, db: AsyncSession, ctx: RequestContext):
        self.db = db
        self.ctx = ctx

    async def get(self, scope: str, key: str) -> IdempotencyKey | None:
        query = select(IdempotencyKey).where(
            and_(
                IdempotencyKey.tenant_id == self.ctx.tenant_id,
                IdempotencyKey.workspace_id == self.ctx.workspace_id,
                IdempotencyKey.user_id == self.ctx.user_id,
                IdempotencyKey.scope == scope,
                IdempotencyKey.key == key,
            )
        )
        result = (await self.db.exec(query)).first()
        if result and not hasattr(result, "request_hash"):
            try:
                return result[0]
            except Exception:
                return None
        return result

    async def create_in_progress(
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
        await self.db.commit()
        return record

    async def update_response(
        self,
        record: IdempotencyKey,
        response_json: dict[str, Any],
        status: str = "completed",
    ) -> IdempotencyKey:
        record.status = status
        record.response_json = response_json
        record.updated_at = utc_now()
        await self.db.commit()
        return record

    async def mark_in_progress(
        self,
        record: IdempotencyKey,
    ) -> IdempotencyKey:
        record.status = "in_progress"
        record.response_json = None
        record.updated_at = utc_now()
        await self.db.commit()
        return record

    async def mark_failed(
        self,
        record: IdempotencyKey,
    ) -> IdempotencyKey:
        record.status = "failed"
        record.updated_at = utc_now()
        await self.db.commit()
        return record
