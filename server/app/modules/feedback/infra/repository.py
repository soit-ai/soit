"""Scope-aware product feedback persistence."""

from typing import TypedDict

from sqlalchemy import desc, func, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.repository import AsyncRepository
from app.kernel.contracts.context import RequestContext
from app.modules.feedback.domain.models import ProductFeedback


class ProductFeedbackSummaryData(TypedDict):
    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_priority: dict[str, int]


class ProductFeedbackRepository(AsyncRepository[ProductFeedback]):
    def __init__(self, db: AsyncSession, ctx: RequestContext) -> None:
        super().__init__(ProductFeedback, db, ctx)

    async def list_for_scope(
        self,
        *,
        creator_id: str | None,
        limit: int,
        offset: int,
        status: str | None = None,
        category: str | None = None,
        priority: str | None = None,
        query_text: str | None = None,
    ) -> list[ProductFeedback]:
        query = self._apply_scope(select(ProductFeedback))
        if creator_id is not None:
            query = query.where(ProductFeedback.created_by == creator_id)
        if status is not None:
            query = query.where(ProductFeedback.status == status)
        if category is not None:
            query = query.where(ProductFeedback.category == category)
        if priority is not None:
            query = query.where(ProductFeedback.priority == priority)
        if query_text:
            escaped = (
                query_text.lower()
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            pattern = f"%{escaped}%"
            query = query.where(
                or_(
                    func.lower(ProductFeedback.title).like(pattern, escape="\\"),
                    func.lower(ProductFeedback.description).like(pattern, escape="\\"),
                )
            )
        results = list(
            (
                await self.db.exec(
                    query.order_by(desc(ProductFeedback.created_at), desc(ProductFeedback.id))
                    .offset(offset)
                    .limit(limit + 1)
                )
            )
            .scalars()
            .all()
        )
        return self._unwrap_all(results)

    async def summarize(self, *, creator_id: str | None) -> ProductFeedbackSummaryData:
        async def _counts(column) -> dict[str, int]:
            query = self._apply_scope(
                select(column, func.count()).select_from(ProductFeedback)
            )
            if creator_id is not None:
                query = query.where(ProductFeedback.created_by == creator_id)
            rows = (await self.db.exec(query.group_by(column))).all()
            return {str(row[0]): int(row[1]) for row in rows}

        status_counts = await _counts(ProductFeedback.status)
        return {
            "total": sum(status_counts.values()),
            "by_status": status_counts,
            "by_category": await _counts(ProductFeedback.category),
            "by_priority": await _counts(ProductFeedback.priority),
        }

    async def save(self, feedback: ProductFeedback) -> ProductFeedback:
        self.db.add(feedback)
        await self.db.commit()
        return feedback
