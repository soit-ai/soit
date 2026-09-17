""" repository

Memory domain repository.
"""


import builtins

from sqlalchemy import and_, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.repository import AsyncRepository
from app.kernel.contracts.context import RequestContext
from app.modules.memory.domain.models import MemoryItem


class MemoryRepository(AsyncRepository[MemoryItem]):
    """Repository for MemoryItem."""

    def __init__(self, db: AsyncSession, ctx: RequestContext):
        super().__init__(MemoryItem, db, ctx)

    async def list(self, limit: int = 20, offset: int = 0) -> list[MemoryItem]:
        query = select(MemoryItem).where(
            and_(
                MemoryItem.tenant_id == self.ctx.tenant_id,
                MemoryItem.workspace_id == self.ctx.workspace_id,
                MemoryItem.deleted_at.is_(None),
            )
        ).order_by(desc(MemoryItem.updated_at)).offset(offset).limit(limit)
        results = list((await self.db.exec(query)).all())
        return self._unwrap_all(results)

    async def list_by_ids(self, ids: builtins.list[str]) -> builtins.list[MemoryItem]:
        if not ids:
            return []
        query = select(MemoryItem).where(
            and_(
                MemoryItem.id.in_(ids),
                MemoryItem.tenant_id == self.ctx.tenant_id,
                MemoryItem.workspace_id == self.ctx.workspace_id,
            )
        )
        results = list((await self.db.exec(query)).all())
        return self._unwrap_all(results)
