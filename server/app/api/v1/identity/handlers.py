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
from app.kernel.commons.errors import (
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.identity.application.schemas import (
    AccountDeletionRequestCreate,
    AccountDeletionRequestResponse,
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    ApiKeyRotateResponse,
    EmailVerificationConfirm,
    InvitationAccept,
    InvitationCreate,
    InvitationResponse,
    MailCapabilityResponse,
    MembershipCreate,
    MembershipResponse,
    MembershipUpdate,
    MfaChallengeResponse,
    MfaConfirmRequest,
    MfaDisableRequest,
    MfaLoginRequest,
    MfaRecoveryCodesResponse,
    MfaSetupResponse,
    MfaStatusResponse,
    MyWorkspaceResponse,
    PasswordChange,
    PasswordResetConfirm,
    PasswordResetRequest,
    PinCreate,
    PinResponse,
    RefreshRequest,
    ResourceGrantCreate,
    ResourceGrantResponse,
    SavedViewCreate,
    SavedViewResponse,
    SavedViewUpdate,
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
from app.modules.identity.application.service import (
    MFA_CHALLENGE_MINUTES,
    IdentityService,
    MfaRequired,
)


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
) -> TokenResponse | MfaChallengeResponse:
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
    except MfaRequired as challenge:
        # Not an error: the password was right, and the caller now owes a code.
        # Returned as a 200 with no access token so a client cannot mistake it
        # for a completed sign-in.
        return MfaChallengeResponse(
            mfa_token=challenge.challenge_token,
            expires_in=MFA_CHALLENGE_MINUTES * 60,
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
        require_mfa=bool(getattr(workspace, "require_mfa", False)),
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

def _link_base(request: Request) -> str:
    """Where a mailed link should point.

    The configured public URL wins, because the request's own host is whatever
    reached the server -- behind a proxy that is an internal name, and a reset
    link nobody outside can open is worse than no link.
    """
    from app.settings.settings import settings

    configured = (settings.system_mail_link_base_url or "").strip()
    if configured:
        return configured
    return str(request.base_url).rstrip("/")


async def get_mail_capability(
    service: IdentityService = Depends(get_identity_service),
) -> MailCapabilityResponse:
    """Report whether this deployment can send mail."""
    return MailCapabilityResponse(mail_enabled=service.mail_is_available())


async def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    service: IdentityService = Depends(get_identity_service),
) -> None:
    """Mail a reset link if that address has an active account.

    Answers the same way either way. Reporting whether the address is
    registered would make this a way to enumerate accounts.
    """
    try:
        await service.request_password_reset(payload.email, _link_base(request))
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


async def confirm_password_reset(
    payload: PasswordResetConfirm,
    service: IdentityService = Depends(get_identity_service),
) -> None:
    """Set a new password from a reset link."""
    try:
        service.complete_password_reset(payload.token, payload.new_password)
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


async def request_email_verification(
    request: Request,
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> None:
    """Mail the caller a link confirming their address."""
    try:
        await service.request_email_verification(ctx, _link_base(request))
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


async def confirm_email_verification(
    payload: EmailVerificationConfirm,
    service: IdentityService = Depends(get_identity_service),
) -> None:
    """Confirm an address from a link."""
    try:
        service.confirm_email_verification(payload.token)
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


async def list_invitations(
    workspace_id: str,
    _ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> list[InvitationResponse]:
    """Pending offers of membership for a workspace.

    The dependency is the read guard; the listing is scoped by the path.
    """
    return [
        InvitationResponse.model_validate(item)
        for item in service.list_invitations(workspace_id)
    ]


async def create_invitation(
    workspace_id: str,
    payload: InvitationCreate,
    request: Request,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> InvitationResponse:
    """Invite an address to a workspace, whether or not it has an account."""
    try:
        invitation = await service.invite_member(
            ctx,
            workspace_id,
            payload.email,
            payload.role,
            _link_base(request),
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return InvitationResponse.model_validate(invitation)


async def revoke_invitation(
    invitation_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> InvitationResponse:
    """Withdraw an offer before it is accepted.

    The workspace comes from the caller's context, which the service checks the
    invitation against: taking it from the path as well would invite the two to
    disagree.
    """
    try:
        return InvitationResponse.model_validate(
            service.revoke_invitation(ctx, invitation_id)
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


async def accept_invitation(
    payload: InvitationAccept,
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> InvitationResponse:
    """Redeem an invitation as the signed-in account."""
    try:
        return InvitationResponse.model_validate(
            service.accept_invitation(payload.token, ctx.user_id)
        )
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except ForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


async def get_account_deletion_request(
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> AccountDeletionRequestResponse | None:
    """The caller's pending closure request, or nothing."""
    request = service.get_deletion_request(ctx)
    return AccountDeletionRequestResponse.model_validate(request) if request else None


async def request_account_deletion(
    payload: AccountDeletionRequestCreate,
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> AccountDeletionRequestResponse:
    """Ask for the account to be closed after a pause it can be withdrawn in."""
    try:
        request = service.request_account_deletion(ctx, payload.reason)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return AccountDeletionRequestResponse.model_validate(request)


async def cancel_account_deletion(
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> AccountDeletionRequestResponse:
    """Withdraw a pending closure request."""
    try:
        return AccountDeletionRequestResponse.model_validate(
            service.cancel_account_deletion(ctx)
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


async def get_mfa_status(
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> MfaStatusResponse:
    """Report whether the caller has a second factor, and its state."""
    enrolment = service.get_mfa(ctx.user_id)
    if enrolment is None:
        return MfaStatusResponse(enabled=False)
    return MfaStatusResponse(
        enabled=enrolment.status == "active",
        pending=enrolment.status == "pending",
        confirmed_at=enrolment.confirmed_at,
        last_used_at=enrolment.last_used_at,
        recovery_codes_remaining=len(enrolment.recovery_hashes_json or []),
    )


async def start_mfa_enrolment(
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> MfaSetupResponse:
    """Begin enrolment. The secret is shown once and never returned again."""
    try:
        secret, uri = service.start_mfa_enrolment(ctx)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return MfaSetupResponse(secret=secret, provisioning_uri=uri)


async def confirm_mfa_enrolment(
    payload: MfaConfirmRequest,
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> MfaRecoveryCodesResponse:
    """Activate the second factor and hand back the recovery codes."""
    try:
        codes = service.confirm_mfa_enrolment(ctx, payload.code)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    return MfaRecoveryCodesResponse(recovery_codes=codes)


async def regenerate_mfa_recovery_codes(
    payload: MfaConfirmRequest,
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> MfaRecoveryCodesResponse:
    """Replace the recovery codes. The old ones stop working immediately."""
    try:
        codes = service.regenerate_recovery_codes(ctx, payload.code)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    return MfaRecoveryCodesResponse(recovery_codes=codes)


async def disable_mfa(
    payload: MfaDisableRequest,
    ctx: RequestContext = Depends(get_current_context),
    service: IdentityService = Depends(get_identity_service),
) -> None:
    """Turn the second factor off, after the password proves who is asking."""
    try:
        service.disable_mfa(ctx, payload.password)
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))


async def complete_mfa_login(
    payload: MfaLoginRequest,
    request: Request,
    service: IdentityService = Depends(get_identity_service),
) -> TokenResponse:
    """Finish a sign-in that stopped at the second factor."""
    from app.settings.settings import settings

    try:
        _user, access_token, workspace_id, refresh_token = service.complete_mfa_login(
            payload.mfa_token,
            payload.code,
            user_agent=request.headers.get("User-Agent"),
            ip_address=_client_ip(request),
        )
    except UnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
        workspace_id=workspace_id,
        refresh_token=refresh_token,
    )


async def list_saved_views(
    surface: str | None = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> list[SavedViewResponse]:
    """List the caller's kept filters, optionally for one screen."""
    return [
        SavedViewResponse.model_validate(view)
        for view in service.list_saved_views(ctx, surface)
    ]


async def create_saved_view(
    data: SavedViewCreate,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> SavedViewResponse:
    """Keep a filter under a name. Saving over a name replaces it."""
    return SavedViewResponse.model_validate(service.create_saved_view(ctx, data))


async def update_saved_view(
    view_id: str,
    data: SavedViewUpdate,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> SavedViewResponse:
    """Rename a kept filter, repoint it, or make it the default."""
    try:
        return SavedViewResponse.model_validate(service.update_saved_view(ctx, view_id, data))
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


async def delete_saved_view(
    view_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> None:
    """Drop one of the caller's kept filters."""
    try:
        service.delete_saved_view(ctx, view_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


async def list_pins(
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> list[PinResponse]:
    """List the caller's pinned objects."""
    return [PinResponse.model_validate(pin) for pin in service.list_pins(ctx)]


async def create_pin(
    data: PinCreate,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> PinResponse:
    """Pin an object. Pinning what is already pinned changes nothing."""
    return PinResponse.model_validate(service.create_pin(ctx, data))


async def delete_pin(
    pin_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> None:
    """Unpin an object."""
    try:
        service.delete_pin(ctx, pin_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


async def list_my_workspaces(
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: IdentityService = Depends(get_identity_service),
) -> list[MyWorkspaceResponse]:
    """List the workspaces the caller belongs to in the current tenant."""
    return [
        MyWorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            description=workspace.description,
            role=role,
            created_at=workspace.created_at,
        )
        for workspace, role in service.list_my_workspaces(ctx)
    ]


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
        member_ids = [membership.user_id for membership in memberships]
        last_active = service.session_repo.last_seen_for_users(member_ids)
        with_mfa = service.mfa_repo.active_user_ids(member_ids)
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
                    mfa_enabled=membership.user_id in with_mfa,
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
