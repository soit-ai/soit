""" dependencies

ModelHub entry dependencies (ctx/auth/policy).
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.infra.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.modelhub.application.service import ModelHubService
from app.wiring.services import build_modelhub_service


def get_modelhub_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ModelHubService:
    """Get modelhub service instance."""
    return build_modelhub_service(db=db, ctx=ctx)
