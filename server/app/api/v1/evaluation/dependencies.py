"""Dependencies for evaluation APIs."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.evaluation.application.service import RegressionEvaluationService
from app.wiring.services import build_evaluation_service


def get_evaluation_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> RegressionEvaluationService:
    return build_evaluation_service(db=db, ctx=ctx)
