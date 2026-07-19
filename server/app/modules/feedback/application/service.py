"""Product feedback application service."""

from app.kernel.commons.errors import ForbiddenError, NotFoundError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.modules.feedback.application.schemas import (
    FeedbackCategory,
    FeedbackPriority,
    FeedbackStatus,
    ProductFeedbackCreate,
    ProductFeedbackSummary,
    ProductFeedbackUpdate,
)
from app.modules.feedback.domain.models import ProductFeedback
from app.modules.feedback.infra.repository import ProductFeedbackRepository


class ProductFeedbackService:
    def __init__(
        self,
        *,
        ctx: RequestContext,
        repository: ProductFeedbackRepository,
    ) -> None:
        self.ctx = ctx
        self.repository = repository

    def create(self, data: ProductFeedbackCreate) -> ProductFeedback:
        return self.repository.create(
            ProductFeedback(
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                title=data.title,
                description=data.description,
                category=data.category,
                priority=data.priority,
                status="open",
                context_json=data.context.model_dump(exclude_none=True),
                created_by=self.ctx.user_id,
                updated_by=self.ctx.user_id,
            )
        )

    def _creator_for_scope(self, scope: str) -> str | None:
        if scope == "workspace" and not self.ctx.is_workspace_owner():
            raise ForbiddenError("Workspace owner role required to list workspace feedback")
        return None if scope == "workspace" else self.ctx.user_id

    def list(
        self,
        *,
        scope: str,
        limit: int,
        offset: int,
        status: str | None = None,
        category: str | None = None,
        priority: str | None = None,
        query_text: str | None = None,
    ) -> list[ProductFeedback]:
        creator_id = self._creator_for_scope(scope)
        return self.repository.list_for_scope(
            creator_id=creator_id,
            limit=limit,
            offset=offset,
            status=status,
            category=category,
            priority=priority,
            query_text=query_text,
        )

    def summary(self, *, scope: str) -> ProductFeedbackSummary:
        creator_id = self._creator_for_scope(scope)
        raw = self.repository.summarize(creator_id=creator_id)
        status_counts: dict[FeedbackStatus, int] = {
            "open": raw["by_status"].get("open", 0),
            "in_progress": raw["by_status"].get("in_progress", 0),
            "resolved": raw["by_status"].get("resolved", 0),
            "closed": raw["by_status"].get("closed", 0),
        }
        category_counts: dict[FeedbackCategory, int] = {
            "bug": raw["by_category"].get("bug", 0),
            "feature": raw["by_category"].get("feature", 0),
            "performance": raw["by_category"].get("performance", 0),
            "usability": raw["by_category"].get("usability", 0),
            "other": raw["by_category"].get("other", 0),
        }
        priority_counts: dict[FeedbackPriority, int] = {
            "low": raw["by_priority"].get("low", 0),
            "medium": raw["by_priority"].get("medium", 0),
            "high": raw["by_priority"].get("high", 0),
            "critical": raw["by_priority"].get("critical", 0),
        }
        return ProductFeedbackSummary(
            total=raw["total"],
            by_status=status_counts,
            by_category=category_counts,
            by_priority=priority_counts,
        )

    def get(self, feedback_id: str) -> ProductFeedback:
        feedback = self.repository.get_by_id(feedback_id)
        if feedback is None:
            raise NotFoundError("Product feedback not found")
        if not self.ctx.is_workspace_owner() and feedback.created_by != self.ctx.user_id:
            raise NotFoundError("Product feedback not found")
        return feedback

    def update(self, feedback_id: str, data: ProductFeedbackUpdate) -> ProductFeedback:
        feedback = self.get(feedback_id)
        now = utc_now()
        if data.priority is not None:
            feedback.priority = data.priority
        if data.status is not None:
            feedback.status = data.status
            if data.status in {"resolved", "closed"}:
                feedback.resolved_by = self.ctx.user_id
                feedback.resolved_at = now
            else:
                feedback.resolved_by = None
                feedback.resolved_at = None
                feedback.resolution_note = None
        if data.resolution_note is not None:
            feedback.resolution_note = data.resolution_note
        feedback.updated_by = self.ctx.user_id
        feedback.updated_at = now
        return self.repository.save(feedback)
