""" handlers

Identity entrypoint handlers.
"""


from typing import Any

from fastapi import Depends, HTTPException, Request, status

from app.api.v1.identity.dependencies import get_identity_service
from app.api.v1.permissions import (
    require_tenant_admin_ctx,
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.kernel.commons.errors import NotFoundError, UnauthorizedError, ValidationError
from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.identity.application.schemas import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    ApiKeyRotateResponse,
    MembershipCreate,
    MembershipResponse,
    MembershipUpdate,
    PasswordChange,
    RefreshRequest,
    ResourceGrantCreate,
    ResourceGrantResponse,
    SessionRevokeAllResponse,
    TenantCreate,
    TenantResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserProfileUpdate,
    UserResponse,
    UserSessionResponse,
    WorkspaceCreate,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.modules.identity.application.service import IdentityService


def _client_ip(request: Request | None) -> str | None:
    """Best-effort client address for the session list.

    Behind a proxy the socket address is the proxy, so the forwarded header is
    preferred when present. It is display-only: nothing is authorized by it,
    which is why a spoofable header is acceptable here.
    """
    if request is None:
        return None
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


async def register(
    user_data: UserCreate,
    request: Request,
    tenant_name: str | None = None,
    service: IdentityService = Depends(get_identity_service),
) -> TokenResponse:
    """Register a new user and create a tenant."""
    from app.settings.settings import settings

    if not settings.allow_public_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled",
        )
    try:
        _, _, access_token, workspace_id, refresh_token = service.register_user(
            user_data,
            tenant_name=tenant_name,
            user_agent=request.headers.get("User-Agent") if request else None,
            ip_address=_client_ip(request),
        )
        from app.settings.settings import settings
        return TokenResponse(
            access_token=access_token,
            expires_in=settings.access_token_expire_minutes * 60,
            workspace_id=workspace_id,
            refresh_token=refresh_token,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

async def login(
    login_data: UserLogin,
    request: Request,
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
        user, access_token, workspace_id, refresh_token = service.authenticate_user(
            login_data.email,
            login_data.password,
            user_agent=request.headers.get("User-Agent") if request else None,
            ip_address=_client_ip(request),
        )
        from app.settings.settings import settings
        return TokenResponse(
            access_token=access_token,
            expires_in=settings.access_token_expire_minutes * 60,
            workspace_id=workspace_id,
            refresh_token=refresh_token,
        )
    except UnauthorizedError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


async def refresh_token(
    payload: RefreshRequest,
    request: Request,
    service: IdentityService = Depends(get_identity_service),
) -> TokenResponse:
    """Exchange a refresh token for a new access token.

    Public by design: the refresh token is the credential, and the caller's
    access token has usually expired by the time this is needed.
    """
    from app.settings.settings import settings

    try:
        access_token, rotated, workspace_id = service.refresh_session(
            payload.refresh_token,
            user_agent=request.headers.get("User-Agent"),
            ip_address=_client_ip(request),
        )
    except UnauthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
        workspace_id=workspace_id,
        refresh_token=rotated,
    )


async def list_sessions(
    request: Request,
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> list[UserSessionResponse]:
    """List the caller's own active sessions."""
    current_id = _current_session_id(request)
    return [
        UserSessionResponse.model_validate(session).model_copy(
            update={"current": session.id == current_id}
        )
        for session in service.list_sessions(ctx)
    ]


async def revoke_session(
    session_id: str,
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> UserSessionResponse:
    """End one of the caller's own sessions."""
    try:
        return UserSessionResponse.model_validate(service.revoke_session(ctx, session_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


async def revoke_all_sessions(
    request: Request,
    keep_current: bool = True,
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> SessionRevokeAllResponse:
    """Sign out everywhere, optionally leaving this device signed in."""
    except_id = _current_session_id(request) if keep_current else None
    return SessionRevokeAllResponse(
        revoked=service.revoke_all_sessions(ctx, except_session_id=except_id)
    )


def _current_session_id(request: Request) -> str | None:
    """Read the session id the caller's own access token names."""
    auth = request.headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        return None
    from app.kernel.identity.auth import decode_jwt_token

    try:
        payload = decode_jwt_token(auth[7:])
    except Exception:
        return None
    session_id = payload.get("sid")
    return str(session_id) if session_id else None


async def get_current_user(
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> UserResponse:
    """Get current user."""
    try:
        user = service.get_user(ctx.user_id)
        payload = UserResponse.model_validate(user).model_dump()
        payload.update(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            tenant_role=ctx.tenant_role,
            workspace_role=ctx.workspace_role,
            profile=getattr(user, "profile_json", {}) or {},
        )
        return UserResponse(**payload)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

async def update_current_user(
    data: UserProfileUpdate,
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> UserResponse:
    """Update current user profile."""
    try:
        user = service.update_user_profile(ctx, data)
        payload = UserResponse.model_validate(user).model_dump()
        payload.update(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            tenant_role=ctx.tenant_role,
            workspace_role=ctx.workspace_role,
            profile=getattr(user, "profile_json", {}) or {},
        )
        return UserResponse(**payload)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

async def change_password(
    data: PasswordChange,
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
):
    """Change current user password."""
    try:
        service.change_password(ctx, data)
    except UnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


def _workspace_response(workspace: Any) -> WorkspaceResponse:
    """Map a workspace domain object without importing the domain layer."""
    return WorkspaceResponse(
        id=workspace.id,
        tenant_id=workspace.tenant_id,
        name=workspace.name,
        description=workspace.description,
        metadata=getattr(workspace, "metadata_json", {}) or {},
        llm_rate_limit_per_minute=workspace.llm_rate_limit_per_minute,
        tool_rate_limit_per_minute=workspace.tool_rate_limit_per_minute,
        llm_daily_quota=workspace.llm_daily_quota,
        tool_daily_quota=workspace.tool_daily_quota,
        created_at=workspace.created_at,
    )


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
    ctx: RequestContext = Depends(require_tenant_admin_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> TenantResponse:
    """Get tenant by ID."""
    _ = ctx
    try:
        tenant = service.get_tenant(tenant_id)
        return TenantResponse.model_validate(tenant)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

async def create_workspace(
    workspace_data: WorkspaceCreate,
    ctx: RequestContext = Depends(require_tenant_admin_ctx),
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
        return _workspace_response(workspace)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


async def list_workspaces(
    tenant_id: str,
    ctx: RequestContext = Depends(require_tenant_admin_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> list[WorkspaceResponse]:
    """List workspaces in tenant."""
    try:
        workspaces = service.list_workspaces(tenant_id=tenant_id, ctx=ctx)
        return [_workspace_response(workspace) for workspace in workspaces]
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

async def get_workspace(
    workspace_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> WorkspaceResponse:
    """Get workspace by ID."""
    try:
        workspace = service.get_workspace(workspace_id=workspace_id, ctx=ctx)
        return _workspace_response(workspace)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

async def update_workspace(
    workspace_id: str,
    data: WorkspaceUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> WorkspaceResponse:
    """Update workspace."""
    try:
        workspace = service.update_workspace(workspace_id, ctx, data)
        return _workspace_response(workspace)
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

async def list_workspace_members(
    workspace_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> list[WorkspaceMemberResponse]:
    """List workspace members."""
    try:
        memberships = service.list_workspace_members(workspace_id, ctx)
        # One read for everyone's last activity rather than a query per member.
        last_active = service.session_repo.last_seen_for_users(
            [membership.user_id for membership in memberships]
        )
        members = []
        for membership in memberships:
            user = service.get_user(membership.user_id)
            members.append(
                WorkspaceMemberResponse(
                    user_id=membership.user_id,
                    email=user.email,
                    name=user.name,
                    role=membership.role,
                    status="active" if user.is_active else "inactive",
                    created_at=membership.created_at,
                    last_active_at=last_active.get(membership.user_id),
                )
            )
        return members
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

async def update_workspace_member(
    workspace_id: str,
    user_id: str,
    data: MembershipUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> MembershipResponse:
    """Update workspace member role."""
    try:
        membership = service.update_workspace_member_role(
            workspace_id=workspace_id,
            user_id=user_id,
            role=data.role,
            ctx=ctx,
        )
        return MembershipResponse.model_validate(membership)
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

async def remove_workspace_member(
    workspace_id: str,
    user_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: IdentityService = Depends(get_identity_service),
):
    """Remove a member from workspace."""
    try:
        service.remove_workspace_member(workspace_id, user_id, ctx)
    except (ValidationError, NotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

async def add_tenant_member(
    tenant_id: str,
    membership_data: MembershipCreate,
    ctx: RequestContext = Depends(require_tenant_admin_ctx),
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
    ctx: RequestContext = Depends(require_workspace_write_ctx),
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


async def create_api_key(
    data: ApiKeyCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> ApiKeyCreateResponse:
    """Create an API key."""
    try:
        api_key, raw_key = service.create_api_key(data, ctx)
        return ApiKeyCreateResponse(
            api_key=raw_key,
            item=ApiKeyResponse.model_validate(api_key),
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


async def list_api_keys(
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: IdentityService = Depends(get_identity_service),
):
    """List API keys for the workspace."""
    from app.infra.db.pagination import PaginatedResponse, parse_page_params

    limit, token_obj = parse_page_params(page_token, page_size)
    offset = token_obj.offset if token_obj else 0
    limit_plus = limit + 1

    keys = service.list_api_keys(ctx, limit=limit_plus, offset=offset)
    has_next = len(keys) > limit
    items = [ApiKeyResponse.model_validate(item) for item in keys[:limit]]
    next_offset = offset + len(items) if has_next else None

    return PaginatedResponse.create(
        items=items,
        page_size=len(items),
        has_next=has_next,
        next_offset=next_offset,
    )


async def revoke_api_key(
    key_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> ApiKeyResponse:
    """Revoke an API key."""
    try:
        api_key = service.revoke_api_key(key_id, ctx)
        return ApiKeyResponse.model_validate(api_key)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


async def rotate_api_key(
    key_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> ApiKeyRotateResponse:
    """Rotate an API key."""
    try:
        api_key, raw_key = service.rotate_api_key(key_id, ctx)
        return ApiKeyRotateResponse(
            api_key=raw_key,
            item=ApiKeyResponse.model_validate(api_key),
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


async def create_resource_grant(
    data: ResourceGrantCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> ResourceGrantResponse:
    """Create or update a resource grant."""
    try:
        grant = service.create_resource_grant(data, ctx)
        return ResourceGrantResponse.model_validate(grant)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


async def list_resource_grants(
    resource_type: str | None = None,
    resource_id: str | None = None,
    limit: int = 500,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> list[ResourceGrantResponse]:
    """List resource grants for one resource, or across the workspace."""
    try:
        grants = service.list_resource_grants(
            resource_type,
            resource_id,
            ctx,
            limit=max(1, min(limit, 1000)),
        )
        return [ResourceGrantResponse.model_validate(item) for item in grants]
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


async def revoke_resource_grant(
    resource_type: str,
    resource_id: str,
    user_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: IdentityService = Depends(get_identity_service),
):
    """Revoke a resource grant."""
    try:
        service.revoke_resource_grant(resource_type, resource_id, user_id, ctx)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
