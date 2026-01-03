""" dependencies

Identity entrypoint dependencies.
"""

from sqlalchemy.orm import Session
from fastapi import Depends

from app.infra.db.session import get_db
from app.kernel.identity.auth import JWTManager
from app.settings.settings import settings
from app.modules.identity.application.service import IdentityService
from app.modules.identity.infra.repository import (
    UserRepository,
    TenantRepository,
    TenantMembershipRepository,
    WorkspaceRepository,
    WorkspaceMembershipRepository,
)
from app.kernel.contracts.context import RequestContext



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
    user_repo = UserRepository(db)
    tenant_repo = TenantRepository(db)
    tenant_membership_repo = TenantMembershipRepository(db)

    workspace_repo_factory = lambda ctx: WorkspaceRepository(db, ctx)
    workspace_membership_repo_factory = lambda ctx: WorkspaceMembershipRepository(db, ctx)

    return IdentityService(
        db=db,
        jwt_manager=jwt_manager,
        user_repo=user_repo,
        tenant_repo=tenant_repo,
        tenant_membership_repo=tenant_membership_repo,
        workspace_repo_factory=workspace_repo_factory,
        workspace_membership_repo_factory=workspace_membership_repo_factory,
    )

