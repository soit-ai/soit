""" dependencies

Security entry dependencies.
"""

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.session import get_async_db
from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.security.application.service import SecurityService
from app.wiring.services import build_security_service


def get_security_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> SecurityService:
    """Get security service instance."""
    return build_security_service(db=db, ctx=ctx)
