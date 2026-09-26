""" dependencies

Identity entrypoint dependencies.
"""

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.session import get_async_db
from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.identity.application.service import IdentityService
from app.modules.identity.application.service_principals import ServicePrincipalService
from app.wiring.services import build_identity_service, build_service_principal_service


def get_identity_service(
    db: AsyncSession = Depends(get_async_db),
) -> IdentityService:
    """Get identity service instance."""
    return build_identity_service(db=db)


def get_service_principal_service(
    ctx: RequestContext = Depends(get_current_context),
    db: AsyncSession = Depends(get_async_db),
) -> ServicePrincipalService:
    """Get the service principal service for the caller's workspace."""
    return build_service_principal_service(db=db, ctx=ctx)
