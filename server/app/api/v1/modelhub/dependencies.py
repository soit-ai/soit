""" dependencies

ModelHub entry dependencies (ctx/auth/policy).
"""

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.session import get_async_db
from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.modelhub.application.service import ModelHubService
from app.modules.modelhub.application.virtual_models import VirtualModelService
from app.wiring.services import build_modelhub_service, build_virtual_model_service


def get_modelhub_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> ModelHubService:
    """Get modelhub service instance."""
    return build_modelhub_service(db=db, ctx=ctx)


def get_virtual_model_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> VirtualModelService:
    """Get the virtual model service."""
    return build_virtual_model_service(db=db, ctx=ctx)
