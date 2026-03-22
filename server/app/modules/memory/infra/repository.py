""" repository

Memory domain repository.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc

from app.infra.db.repository import Repository
from app.kernel.contracts.context import RequestContext
from app.modules.memory.domain.models import MemoryItem


class MemoryRepository(Repository[MemoryItem]):
    """Repository for MemoryItem."""

    def __init__(self, db: Session, ctx: RequestContext):
        super().__init__(MemoryItem, db, ctx)

    def list(self, limit: int = 20, offset: int = 0) -> List[MemoryItem]:
        query = select(MemoryItem).where(
            and_(
                MemoryItem.tenant_id == self.ctx.tenant_id,
                MemoryItem.workspace_id == self.ctx.workspace_id,
                MemoryItem.deleted_at.is_(None),
            )
        ).order_by(desc(MemoryItem.updated_at)).offset(offset).limit(limit)
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)

    def list_by_ids(self, ids: List[str]) -> List[MemoryItem]:
        if not ids:
            return []
        query = select(MemoryItem).where(
            and_(
                MemoryItem.id.in_(ids),
                MemoryItem.tenant_id == self.ctx.tenant_id,
                MemoryItem.workspace_id == self.ctx.workspace_id,
            )
        )
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)
