""" handlers

Identity entrypoint handlers.
"""

from typing import List
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ValidationError, NotFoundError, UnauthorizedError
from app.middleware.auth import get_current_context
from app.modules.identity.application.service import IdentityService
from app.modules.identity.application.schemas import (
    UserCreate,
    UserLogin,
    UserResponse,
    TenantCreate,
    TenantResponse,
    WorkspaceCreate,
    WorkspaceResponse,
    MembershipCreate,
    MembershipResponse,
    TokenResponse,
)
from app.modules.identity.infrastructure.repository import (
    UserRepository,
    TenantRepository,
    WorkspaceRepository,
    TenantMembershipRepository,
    WorkspaceMembershipRepository,
)
from app.infra.db.session import get_db
from app.api.v1.identity.dependencies import get_identity_service


async def register(
    user_data: UserCreate,
    tenant_name: str | None = None,
    service: IdentityService = Depends(get_identity_service),
) -> dict:
    """Register a new user.
    
    Args:
        user_data: User creation data.
        tenant_name: Optional tenant name.
        service: Identity service.
        
    Returns:
        Dictionary with user, tenant, and token.
    """
    try:
        user, tenant, access_token = service.register_user(user_data, tenant_name)
        return {
            "user": UserResponse.model_validate(user),
            "tenant": TenantResponse.model_validate(tenant) if tenant else None,
            "access_token": access_token,
            "token_type": "bearer",
        }
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


async def login(
    login_data: UserLogin,
    service: IdentityService = Depends(get_identity_service),
) -> TokenResponse:
    """Login user.
    
    Args:
        login_data: Login credentials.
        service: Identity service.
        
    Returns:
        Token response.
    """
    try:
        user, access_token = service.authenticate_user(
            login_data.email,
            login_data.password,
        )
        from app.settings.settings import settings
        return TokenResponse(
            access_token=access_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )
    except UnauthorizedError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


async def get_current_user(
    ctx: RequestContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Get current user.
    
    Args:
        ctx: Request context.
        db: Database session.
        
    Returns:
        User response.
    """
    user_repo = UserRepository(db)
    user = user_repo.get_by_id(ctx.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse.model_validate(user)


async def create_tenant(
    tenant_data: TenantCreate,
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> TenantResponse:
    """Create a new tenant.
    
    Args:
        tenant_data: Tenant creation data.
        ctx: Request context.
        service: Identity service.
        
    Returns:
        Tenant response.
    """
    try:
        tenant = service.create_tenant(tenant_data, ctx.user_id)
        return TenantResponse.model_validate(tenant)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


async def get_tenant(
    tenant_id: str,
    ctx: RequestContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> TenantResponse:
    """Get tenant by ID.
    
    Args:
        tenant_id: Tenant ID.
        ctx: Request context.
        db: Database session.
        
    Returns:
        Tenant response.
    """
    # Check access
    if ctx.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    tenant_repo = TenantRepository(db)
    tenant = tenant_repo.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return TenantResponse.model_validate(tenant)


async def create_workspace(
    workspace_data: WorkspaceCreate,
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> WorkspaceResponse:
    """Create a new workspace.
    
    Args:
        workspace_data: Workspace creation data.
        ctx: Request context.
        service: Identity service.
        
    Returns:
        Workspace response.
    """
    try:
        workspace = service.create_workspace(workspace_data, ctx)
        return WorkspaceResponse.model_validate(workspace)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


async def list_workspaces(
    ctx: RequestContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> List[WorkspaceResponse]:
    """List workspaces in tenant.
    
    Args:
        ctx: Request context.
        db: Database session.
        
    Returns:
        List of workspace responses.
    """
    workspace_repo = WorkspaceRepository(db, ctx)
    workspaces = workspace_repo.list_by_tenant()
    return [WorkspaceResponse.model_validate(w) for w in workspaces]


async def get_workspace(
    workspace_id: str,
    ctx: RequestContext = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> WorkspaceResponse:
    """Get workspace by ID.
    
    Args:
        workspace_id: Workspace ID.
        ctx: Request context.
        db: Database session.
        
    Returns:
        Workspace response.
    """
    workspace_repo = WorkspaceRepository(db, ctx)
    workspace = workspace_repo.get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    return WorkspaceResponse.model_validate(workspace)


async def add_tenant_member(
    tenant_id: str,
    membership_data: MembershipCreate,
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> MembershipResponse:
    """Add a member to a tenant.
    
    Args:
        tenant_id: Tenant ID.
        membership_data: Membership creation data.
        ctx: Request context.
        service: Identity service.
        
    Returns:
        Membership response.
    """
    try:
        membership = service.add_tenant_member(tenant_id, membership_data, ctx)
        return MembershipResponse.model_validate(membership)
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


async def add_workspace_member(
    workspace_id: str,
    membership_data: MembershipCreate,
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> MembershipResponse:
    """Add a member to a workspace.
    
    Args:
        workspace_id: Workspace ID.
        membership_data: Membership creation data.
        ctx: Request context.
        service: Identity service.
        
    Returns:
        Membership response.
    """
    try:
        membership = service.add_workspace_member(workspace_id, membership_data, ctx)
        return MembershipResponse.model_validate(membership)
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

