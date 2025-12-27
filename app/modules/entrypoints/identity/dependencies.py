""" dependencies

Identity entrypoint dependencies.
"""

from sqlalchemy.orm import Session
from fastapi import Depends

from app.kernel.db.session import get_db
from app.kernel.identity.auth import JWTManager
from app.kernel.config.settings import settings
from app.modules.domains.identity.service import IdentityService


_jwt_manager: JWTManager | None = None


def get_jwt_manager() -> JWTManager:
    """Get or create JWT manager instance.
    
    Returns:
        JWTManager instance.
    """
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTManager(
            secret_key=settings.secret_key,
            algorithm=settings.jwt_algorithm,
            access_token_expire_minutes=settings.access_token_expire_minutes,
        )
    return _jwt_manager


def get_identity_service(
    db: Session = Depends(get_db),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
) -> IdentityService:
    """Get identity service instance.
    
    Args:
        db: Database session.
        jwt_manager: JWT manager.
        
    Returns:
        IdentityService instance.
    """
    return IdentityService(db, jwt_manager)

