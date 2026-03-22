"""Dependencies for observability governance APIs."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.observability.application.service import ObservabilityService
from app.wiring.services import build_observability_service


def get_observability_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ObservabilityService:
    return build_observability_service(db=db, ctx=ctx)
