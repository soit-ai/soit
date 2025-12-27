""" dependencies

ModelHub entry dependencies (ctx/auth/policy).
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.domains.modelhub.service import ModelHubService


def get_modelhub_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> ModelHubService:
    """Get model hub service instance.
    
    Args:
        ctx: Request context.
        db: Database session.
        
    Returns:
        ModelHubService instance.
    """
    return ModelHubService(db, ctx)

