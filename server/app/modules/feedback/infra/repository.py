"""Scope-aware product feedback persistence."""

from typing import TypedDict

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.infra.db.repository import Repository
from app.kernel.contracts.context import RequestContext
from app.modules.feedback.domain.models import ProductFeedback


class ProductFeedbackSummaryData(TypedDict):
    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_priority: dict[str, int]


class ProductFeedbackRepository(Repository[ProductFeedback]):
    def __init__(self, db: Session, ctx: RequestContext) -> None:
        super().__init__(ProductFeedback, db, ctx)

    def list_for_scope(
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
            self.db.exec(
                query.order_by(desc(ProductFeedback.created_at), desc(ProductFeedback.id))
                .offset(offset)
                .limit(limit + 1)
            ).all()
        )
        return self._unwrap_all(results)

    def summarize(self, *, creator_id: str | None) -> ProductFeedbackSummaryData:
        def _counts(column) -> dict[str, int]:
            query = self._apply_scope(
                select(column, func.count()).select_from(ProductFeedback)
            )
            if creator_id is not None:
                query = query.where(ProductFeedback.created_by == creator_id)
            rows = self.db.exec(query.group_by(column)).all()
            return {str(row[0]): int(row[1]) for row in rows}

        status_counts = _counts(ProductFeedback.status)
        return {
            "total": sum(status_counts.values()),
            "by_status": status_counts,
            "by_category": _counts(ProductFeedback.category),
            "by_priority": _counts(ProductFeedback.priority),
        }

    def save(self, feedback: ProductFeedback) -> ProductFeedback:
        self.db.add(feedback)
        self.db.commit()
        self.db.refresh(feedback)
        return feedback
