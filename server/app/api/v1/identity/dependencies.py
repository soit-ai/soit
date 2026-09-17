""" dependencies

Identity entrypoint dependencies.
"""

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.session import get_async_db
from app.modules.identity.application.service import IdentityService
from app.wiring.services import build_identity_service


def get_identity_service(
    db: AsyncSession = Depends(get_async_db),
) -> IdentityService:
    """Get identity service instance."""
    return build_identity_service(db=db)
