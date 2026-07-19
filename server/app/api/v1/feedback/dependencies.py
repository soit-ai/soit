"""Product feedback API dependencies."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.feedback.application.service import ProductFeedbackService
from app.modules.feedback.infra.repository import ProductFeedbackRepository


def get_product_feedback_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ProductFeedbackService:
    return ProductFeedbackService(
        ctx=ctx,
        repository=ProductFeedbackRepository(db, ctx),
    )
