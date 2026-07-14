"""Dependencies for observe governance APIs."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.observe.application.service import ObserveService
from app.wiring.services import build_observe_service


def get_observe_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ObserveService:
    return build_observe_service(db=db, ctx=ctx)
