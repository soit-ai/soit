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
    service: IdentityService = Depends(get_identity_service),
) -> UserResponse:
    """Get current user."""
    try:
        user = service.get_user(ctx.user_id)
        return UserResponse.model_validate(user)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

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
    service: IdentityService = Depends(get_identity_service),
) -> TenantResponse:
    """Get tenant by ID."""
    try:
        tenant = service.get_tenant(tenant_id)
        return TenantResponse.model_validate(tenant)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

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
    tenant_id: str,
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> List[WorkspaceResponse]:
    """List workspaces in tenant."""
    try:
        workspaces = service.list_workspaces(tenant_id=tenant_id, ctx=ctx)
        return [WorkspaceResponse.model_validate(w) for w in workspaces]
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

async def get_workspace(
    workspace_id: str,
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> WorkspaceResponse:
    """Get workspace by ID."""
    try:
        workspace = service.get_workspace(workspace_id=workspace_id, ctx=ctx)
        return WorkspaceResponse.model_validate(workspace)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

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

