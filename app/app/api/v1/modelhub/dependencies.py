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
from app.modules.modelhub.infra.repository import ModelRepository



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
    model_repo = ModelRepository(db, ctx)
    return ModelHubService(db, ctx, model_repo)

