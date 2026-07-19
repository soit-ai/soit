"""Workspace-local product feedback routes."""

from typing import Literal

from fastapi import APIRouter, Depends, status

from app.api.v1.feedback.dependencies import get_product_feedback_service
from app.api.v1.permissions import (
    require_workspace_owner_ctx,
    require_workspace_read_ctx,
)
from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.contracts.context import RequestContext
from app.modules.feedback.application.schemas import (
    ProductFeedbackCreate,
    ProductFeedbackResponse,
    ProductFeedbackSummary,
    ProductFeedbackUpdate,
)
from app.modules.feedback.application.service import ProductFeedbackService

router = APIRouter()


@router.post("", response_model=ProductFeedbackResponse, status_code=status.HTTP_201_CREATED)
async def create_product_feedback(
    payload: ProductFeedbackCreate,
    _ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ProductFeedbackService = Depends(get_product_feedback_service),
) -> ProductFeedbackResponse:
    return ProductFeedbackResponse.model_validate(service.create(payload))


@router.get("", response_model=PaginatedResponse[ProductFeedbackResponse])
async def list_product_feedback(
    scope: Literal["mine", "workspace"] = "mine",
    status: Literal["open", "in_progress", "resolved", "closed"] | None = None,
    category: Literal["bug", "feature", "performance", "usability", "other"] | None = None,
    priority: Literal["low", "medium", "high", "critical"] | None = None,
    q: str | None = None,
    page_token: str | None = None,
    page_size: int = 20,
    _ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ProductFeedbackService = Depends(get_product_feedback_service),
) -> PaginatedResponse[ProductFeedbackResponse]:
    limit, token = parse_page_params(page_token, page_size)
    offset = token.offset if token else 0
    rows = service.list(
        scope=scope,
        limit=limit,
        offset=offset,
        status=status,
        category=category,
        priority=priority,
        query_text=q.strip() if q else None,
    )
    has_next = len(rows) > limit
    items = [ProductFeedbackResponse.model_validate(row) for row in rows[:limit]]
    return PaginatedResponse[ProductFeedbackResponse].create(
        items=items,
        page_size=limit,
        has_next=has_next,
        next_offset=offset + len(items) if has_next else None,
    )


@router.get("/summary", response_model=ProductFeedbackSummary)
async def summarize_product_feedback(
    scope: Literal["mine", "workspace"] = "mine",
    _ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ProductFeedbackService = Depends(get_product_feedback_service),
) -> ProductFeedbackSummary:
    return service.summary(scope=scope)


@router.get("/{feedback_id}", response_model=ProductFeedbackResponse)
async def get_product_feedback(
    feedback_id: str,
    _ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ProductFeedbackService = Depends(get_product_feedback_service),
) -> ProductFeedbackResponse:
    return ProductFeedbackResponse.model_validate(service.get(feedback_id))


@router.patch("/{feedback_id}", response_model=ProductFeedbackResponse)
async def update_product_feedback(
    feedback_id: str,
    payload: ProductFeedbackUpdate,
    _ctx: RequestContext = Depends(require_workspace_owner_ctx),
    service: ProductFeedbackService = Depends(get_product_feedback_service),
) -> ProductFeedbackResponse:
    return ProductFeedbackResponse.model_validate(service.update(feedback_id, payload))
