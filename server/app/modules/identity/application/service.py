""" service

Identity domain business logic.
"""

import asyncio
import hashlib
import logging
import secrets
import threading
from collections.abc import Callable
from datetime import UTC, timedelta

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.kernel.commons.errors import (
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity import sealing, totp
from app.kernel.identity.api_key_scopes import normalize_scopes
from app.kernel.identity.auth import JWTManager
from app.kernel.identity.rbac import (
    TENANT_ROLE_ADMIN,
    TENANT_ROLE_DEV,
    TENANT_ROLE_OWNER,
    TENANT_ROLES,
    WORKSPACE_ROLE_ADMIN,
    WORKSPACE_ROLE_DEV,
    WORKSPACE_ROLE_OWNER,
    WORKSPACE_ROLE_VIEWER,
    WORKSPACE_ROLES,
)
from app.kernel.ports.mail.interface import MailMessage, MailPort
from app.kernel.runtime.db.models.audit import AuditEvent
from app.modules.identity.application.ports import (
    AccountDeletionRequestRepositoryPort,
    ApiKeyRepositoryPort,
    IdentityTokenRepositoryPort,
    PinnedObjectRepositoryPort,
    ResourceGrantRepositoryPort,
    SavedViewRepositoryPort,
    TenantMembershipRepositoryPort,
    TenantRepositoryPort,
    UserMfaRepositoryPort,
    UserRepositoryPort,
    UserSessionRepositoryPort,
    WorkspaceInvitationRepositoryPort,
    WorkspaceMembershipRepositoryPort,
    WorkspaceRepositoryPort,
)
from app.modules.identity.application.schemas import (
    ApiKeyCreate,
    MembershipCreate,
    PasswordChange,
    PinCreate,
    ResourceGrantCreate,
    SavedViewCreate,
    SavedViewUpdate,
    TenantCreate,
    UserCreate,
    UserProfileUpdate,
    WorkspaceCreate,
    WorkspaceUpdate,
)
from app.modules.identity.domain.models import (
    AccountDeletionRequest,
    ApiKey,
    IdentityToken,
    PinnedObject,
    ResourceGrant,
    SavedView,
    Tenant,
    TenantMembership,
    User,
    UserMfa,
    UserSession,
    Workspace,
    WorkspaceInvitation,
    WorkspaceMembership,
)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

MFA_CHALLENGE_PURPOSE = "mfa_challenge"
"""Marks a token that may only complete a sign-in, never authorize a request."""

MFA_CHALLENGE_MINUTES = 5
"""How long the gap between password and code may stay open."""

PASSWORD_RESET_MINUTES = 30
"""A reset link is short-lived: it is a password in the recipient's mailbox."""

EMAIL_VERIFICATION_MINUTES = 60 * 24
"""Confirming an address is not urgent, so the link lasts a day."""

INVITATION_DAYS = 14
"""How long an offer of membership stays open."""

logger = logging.getLogger(__name__)


class MfaRequired(Exception):
    """Raised instead of a session when a second factor still has to be proved.

    Carries the challenge token rather than a message: the caller needs it to
    continue, and an exception is how the password path refuses to hand back a
    session without saying "wrong password".
    """

    def __init__(self, challenge_token: str) -> None:
        super().__init__("Two-factor authentication is required")
        self.challenge_token = challenge_token


class IdentityService:
    """Service for identity management."""

    def __init__(
        self,
        db: Session,
        jwt_manager: JWTManager,
        user_repo: UserRepositoryPort,
        tenant_repo: TenantRepositoryPort,
        tenant_membership_repo: TenantMembershipRepositoryPort,
        workspace_repo_factory: Callable[[RequestContext], WorkspaceRepositoryPort],
        workspace_membership_repo_factory: Callable[[RequestContext], WorkspaceMembershipRepositoryPort],
        api_key_repo: ApiKeyRepositoryPort,
        resource_grant_repo_factory: Callable[[RequestContext], ResourceGrantRepositoryPort],
        session_repo: UserSessionRepositoryPort,
        saved_view_repo_factory: Callable[[RequestContext], SavedViewRepositoryPort],
        pin_repo_factory: Callable[[RequestContext], PinnedObjectRepositoryPort],
        mfa_repo: UserMfaRepositoryPort,
        deletion_repo: AccountDeletionRequestRepositoryPort,
        token_repo: IdentityTokenRepositoryPort,
        invitation_repo: WorkspaceInvitationRepositoryPort,
        mail_port: MailPort | None = None,
    ):
        """Initialize identity service.

        Args:
            db: Database session.
            jwt_manager: JWT manager instance.
        """
        self.db = db
        self.jwt_manager = jwt_manager
        self.user_repo = user_repo
        self.tenant_repo = tenant_repo
        self.tenant_membership_repo = tenant_membership_repo
        self.workspace_repo_factory = workspace_repo_factory
        self.workspace_membership_repo_factory = workspace_membership_repo_factory
        self.api_key_repo = api_key_repo
        self.resource_grant_repo_factory = resource_grant_repo_factory
        self.session_repo = session_repo
        self.saved_view_repo_factory = saved_view_repo_factory
        self.pin_repo_factory = pin_repo_factory
        self.mfa_repo = mfa_repo
        self.deletion_repo = deletion_repo
        self.token_repo = token_repo
        self.invitation_repo = invitation_repo
        self.mail_port = mail_port

    def _run_async(self, coro):
        """Run coroutine to completion from sync contexts."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        result = {}
        error = {}

        def runner() -> None:
            try:
                result["value"] = asyncio.run(coro)
            except Exception as exc:
                error["error"] = exc

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()

        if "error" in error:
            raise error["error"]
        return result.get("value")

    def _normalize_actions(self, actions: list[str]) -> list[str]:
        normalized = []
        seen = set()
        for action in actions:
            value = action.strip().lower()
            if not value:
                continue
            if value in seen:
                continue
            normalized.append(value)
            seen.add(value)
        return normalized

    def _resolve_workspace_role(self, tenant_role: str | None) -> str:
        if tenant_role == TENANT_ROLE_OWNER:
            return WORKSPACE_ROLE_OWNER
        if tenant_role == TENANT_ROLE_ADMIN:
            return WORKSPACE_ROLE_ADMIN
        if tenant_role == TENANT_ROLE_DEV:
            return WORKSPACE_ROLE_DEV
        return WORKSPACE_ROLE_VIEWER

    def _ensure_workspace_membership(
        self,
        *,
        tenant_id: str,
        user_id: str,
        tenant_role: str | None,
    ) -> tuple[str, str]:
        ctx = RequestContext(
            tenant_id=tenant_id,
            workspace_id="bootstrap",
            user_id=user_id,
            tenant_role=tenant_role,
        )
        membership_repo = self.workspace_membership_repo_factory(ctx)
        memberships = membership_repo.get_by_user(user_id)
        if memberships:
            memberships.sort(key=lambda item: item.created_at)
            membership = memberships[0]
            return membership.workspace_id, membership.role

        workspace_repo = self.workspace_repo_factory(ctx)
        workspaces = workspace_repo.list_by_tenant()
        if workspaces:
            workspace = workspaces[0]
        else:
            workspace = Workspace(
                name="default",
                description="Default workspace",
            )
            workspace = workspace_repo.create(workspace)

        role = self._resolve_workspace_role(tenant_role)
        membership_repo.create(
            WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=user_id,
                role=role,
            )
        )
        return workspace.id, role

    def register_user(
        self,
        user_data: UserCreate,
        tenant_name: str | None = None,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[User, Tenant, str, str, str]:
        """Register a new user and create a tenant.

        Args:
            user_data: User creation data.
            tenant_name: Optional tenant name (creates tenant if provided).

        Returns:
            Tuple of (User, Tenant, access_token, workspace_id, refresh_token).

        Raises:
            ValidationError: If user already exists or validation fails.
        """
        # Check if user already exists
        existing_user = self.user_repo.get_by_email(user_data.email)
        if existing_user:
            raise ValidationError("User with this email already exists")

        # Create user
        password_hash = pwd_context.hash(user_data.password)
        user = User(
            email=user_data.email,
            password_hash=password_hash,
            name=user_data.name,
        )
        user = self.user_repo.create(user)

        if not tenant_name:
            tenant_name = f"{user.id}-tenant"
        existing_tenant = self.tenant_repo.get_by_name(tenant_name)
        if existing_tenant:
            raise ValidationError("Tenant with this name already exists")
        tenant = Tenant(name=tenant_name)
        tenant = self.tenant_repo.create(tenant)

        membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=user.id,
            role=TENANT_ROLE_OWNER,
        )
        self.tenant_membership_repo.create(membership)

        workspace_id, workspace_role = self._ensure_workspace_membership(
            tenant_id=tenant.id,
            user_id=user.id,
            tenant_role=TENANT_ROLE_OWNER,
        )

        session, refresh_token = self._issue_session(
            user_id=user.id,
            tenant_id=tenant.id,
            workspace_id=workspace_id,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        access_token = self.jwt_manager.create_access_token(
            user_id=user.id,
            tenant_id=tenant.id,
            workspace_id=workspace_id,
            tenant_role=TENANT_ROLE_OWNER,
            workspace_role=workspace_role,
            session_id=session.id,
        )

        return user, tenant, access_token, workspace_id, refresh_token

    def authenticate_user(
        self,
        email: str,
        password: str,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[User, str, str, str]:
        """Authenticate a user.

        Args:
            email: User email.
            password: User password.

        Returns:
            Tuple of (User, access_token, workspace_id, refresh_token).

        Raises:
            UnauthorizedError: If authentication fails.
        """
        user = self.user_repo.get_by_email(email)
        if not user:
            raise UnauthorizedError("Invalid email or password")

        if not user.is_active:
            raise UnauthorizedError("User account is inactive")

        if not pwd_context.verify(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")

        # Get user's primary tenant (first membership)
        memberships = self.tenant_membership_repo.get_by_user(user.id)
        if not memberships:
            raise UnauthorizedError("User has no tenant membership")
        memberships.sort(key=lambda item: item.created_at)
        tenant_id = memberships[0].tenant_id
        tenant_role = memberships[0].role

        if self.mfa_is_active(user.id):
            # Stop here. A password alone must not produce a session, so the
            # caller gets a short-lived challenge instead and comes back with
            # a code.
            raise MfaRequired(self._issue_mfa_challenge(user.id, tenant_id))

        workspace_id, workspace_role = self._ensure_workspace_membership(
            tenant_id=tenant_id,
            user_id=user.id,
            tenant_role=tenant_role,
        )

        session, refresh_token = self._issue_session(
            user_id=user.id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        access_token = self.jwt_manager.create_access_token(
            user_id=user.id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            tenant_role=tenant_role,
            workspace_role=workspace_role,
            session_id=session.id,
        )

        return user, access_token, workspace_id, refresh_token

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_refresh_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _issue_session(
        self,
        *,
        user_id: str,
        tenant_id: str,
        workspace_id: str | None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[UserSession, str]:
        """Open a session and mint the refresh token that renews it.

        The token is returned once; only its hash is kept, so a leaked database
        cannot be replayed as a sign-in.
        """
        refresh_token = secrets.token_urlsafe(48)
        session = UserSession(
            tenant_id=tenant_id,
            user_id=user_id,
            workspace_id=workspace_id,
            refresh_token_hash=self._hash_refresh_token(refresh_token),
            user_agent=(user_agent or "")[:512] or None,
            ip_address=(ip_address or "")[:64] or None,
            expires_at=utc_now() + timedelta(days=self._refresh_token_days()),
        )
        return self.session_repo.create(session), refresh_token

    @staticmethod
    def _refresh_token_days() -> int:
        from app.settings.settings import settings

        return max(1, int(settings.refresh_token_expire_days))

    def _session_is_live(self, session: UserSession) -> bool:
        if session.status != "active":
            return False
        expires_at = session.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at is None or expires_at > utc_now()

    def refresh_session(
        self,
        refresh_token: str,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[str, str, str | None]:
        """Exchange a refresh token for a new access token.

        The refresh token is rotated on every use, and presenting a rotated-out
        token ends the session: either it was replayed by someone who should
        not have it, or the real client lost the race and needs to sign in
        again. Both are safer resolved by ending the session than by guessing.

        Returns:
            (access_token, new_refresh_token, workspace_id)
        """
        session = self.session_repo.get_by_refresh_hash(
            self._hash_refresh_token(refresh_token)
        )
        if session is None:
            raise UnauthorizedError("Invalid refresh token")
        if not self._session_is_live(session):
            raise UnauthorizedError("Session has ended")

        user = self.user_repo.get_by_id(session.user_id)
        if user is None or not user.is_active:
            self._end_session(session, revoked_by="system")
            raise UnauthorizedError("User account is inactive")

        memberships = self.tenant_membership_repo.get_by_user(user.id)
        membership = next(
            (item for item in memberships if item.tenant_id == session.tenant_id),
            None,
        )
        if membership is None:
            self._end_session(session, revoked_by="system")
            raise UnauthorizedError("User is no longer a member of this tenant")

        workspace_id, workspace_role = self._ensure_workspace_membership(
            tenant_id=session.tenant_id,
            user_id=user.id,
            tenant_role=membership.role,
        )

        rotated = secrets.token_urlsafe(48)
        session.refresh_token_hash = self._hash_refresh_token(rotated)
        session.last_seen_at = utc_now()
        session.workspace_id = workspace_id
        if user_agent:
            session.user_agent = user_agent[:512]
        if ip_address:
            session.ip_address = ip_address[:64]
        self.session_repo.save(session)

        access_token = self.jwt_manager.create_access_token(
            user_id=user.id,
            tenant_id=session.tenant_id,
            workspace_id=workspace_id,
            tenant_role=membership.role,
            workspace_role=workspace_role,
            session_id=session.id,
        )
        return access_token, rotated, workspace_id

    def list_sessions(self, ctx: RequestContext) -> list[UserSession]:
        """List the caller's own sessions, most recently active first."""
        return self.session_repo.list_by_user(ctx.user_id)

    def _end_session(self, session: UserSession, *, revoked_by: str) -> UserSession:
        session.status = "revoked"
        session.revoked_at = utc_now()
        session.revoked_by = revoked_by
        # Rotating the hash to an unmatchable value means a refresh token in
        # flight cannot be presented again even if the status check is missed.
        session.refresh_token_hash = f"revoked:{session.id}:{secrets.token_hex(8)}"
        return self.session_repo.save(session)

    def revoke_session(self, ctx: RequestContext, session_id: str) -> UserSession:
        """End one of the caller's own sessions."""
        session = self.session_repo.get_by_id(session_id)
        if session is None or session.user_id != ctx.user_id:
            # Not found and not yours are the same answer: a caller must not be
            # able to probe for other people's session ids.
            raise NotFoundError("Session not found")
        if session.status != "active":
            return session
        ended = self._end_session(session, revoked_by=ctx.user_id)
        self._log_session_audit(ctx, ended, operation="revoke")
        return ended

    def revoke_all_sessions(
        self,
        ctx: RequestContext,
        *,
        except_session_id: str | None = None,
    ) -> int:
        """End every session the caller has, optionally sparing the current one."""
        ended = 0
        for session in self.session_repo.list_by_user(ctx.user_id):
            if except_session_id and session.id == except_session_id:
                continue
            self._end_session(session, revoked_by=ctx.user_id)
            ended += 1
        if ended:
            self._log_session_audit(ctx, None, operation="revoke_all", count=ended)
        return ended

    def _log_session_audit(
        self,
        ctx: RequestContext,
        session: UserSession | None,
        *,
        operation: str,
        count: int | None = None,
    ) -> None:
        payload: dict = {"operation": operation}
        if count is not None:
            payload["count"] = count
        self.db.add(
            AuditEvent(
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                event_type="identity.session.revoked",
                resource_type="user_session",
                resource_id=session.id if session else None,
                operation=operation,
                actor_user_id=ctx.user_id,
                subject_user_id=session.user_id if session else ctx.user_id,
                outcome="revoked",
                scope="tenant",
                payload_json=payload,
            )
        )
        self.db.commit()

    # ------------------------------------------------------------------
    # Closing an account
    # ------------------------------------------------------------------

    def get_deletion_request(self, ctx: RequestContext) -> AccountDeletionRequest | None:
        """The caller's pending closure request, if they have one."""
        return self.deletion_repo.get_pending_for_user(ctx.user_id)

    def request_account_deletion(
        self,
        ctx: RequestContext,
        reason: str | None = None,
    ) -> AccountDeletionRequest:
        """Ask for the account to be closed, after a pause.

        Refused for the last owner of a tenant: closing it would leave the
        tenant with nobody who can administer it, and every other member locked
        out of changes only an owner can make. Hand the role over first.
        """
        from app.settings.settings import settings

        existing = self.deletion_repo.get_pending_for_user(ctx.user_id)
        if existing is not None:
            return existing

        if self._is_last_tenant_owner(ctx.tenant_id, ctx.user_id):
            raise ValidationError(
                "Transfer ownership of the tenant before closing this account"
            )

        grace_days = max(0, int(settings.account_deletion_grace_days))
        request = self.deletion_repo.save(
            AccountDeletionRequest(
                user_id=ctx.user_id,
                tenant_id=ctx.tenant_id,
                reason=(reason or "").strip()[:512] or None,
                execute_after=utc_now() + timedelta(days=grace_days),
            )
        )
        self._log_deletion_audit(ctx, request, operation="request")
        return request

    def cancel_account_deletion(self, ctx: RequestContext) -> AccountDeletionRequest:
        """Withdraw a pending closure request."""
        request = self.deletion_repo.get_pending_for_user(ctx.user_id)
        if request is None:
            raise NotFoundError("No closure request is pending")
        request.status = "cancelled"
        request.cancelled_at = utc_now()
        request.updated_at = utc_now()
        saved = self.deletion_repo.save(request)
        self._log_deletion_audit(ctx, saved, operation="cancel")
        return saved

    def _is_last_tenant_owner(self, tenant_id: str, user_id: str) -> bool:
        memberships = self.tenant_membership_repo.get_by_tenant(tenant_id)
        owners = [item for item in memberships if item.role == TENANT_ROLE_OWNER]
        return len(owners) == 1 and owners[0].user_id == user_id

    def execute_account_deletion(self, request: AccountDeletionRequest) -> AccountDeletionRequest:
        """Close the account: end its access, keep what it did.

        Sessions end, API keys are revoked, the second factor is dropped and
        the user is deactivated. Runs, audits and approvals are untouched --
        they record who authorised what, and a closure that rewrote them would
        make the audit trail worth nothing.
        """
        user = self.user_repo.get_by_id(request.user_id)
        if user is not None:
            user.is_active = False
            user.updated_at = utc_now()
            self.user_repo.update(user)

        for session in self.session_repo.list_by_user(request.user_id):
            self._end_session(session, revoked_by="account_closure")

        for key in self.api_key_repo.list_by_user(request.user_id):
            if key.status == "active":
                key.status = "revoked"
                key.revoked_at = utc_now()
                self.api_key_repo.update(key)

        enrolment = self.mfa_repo.get_by_user(request.user_id)
        if enrolment is not None:
            self.mfa_repo.delete(enrolment)

        request.status = "executed"
        request.executed_at = utc_now()
        request.updated_at = utc_now()
        saved = self.deletion_repo.save(request)
        self.db.add(
            AuditEvent(
                tenant_id=request.tenant_id,
                workspace_id=None,
                event_type="identity.account.closed",
                resource_type="user",
                resource_id=request.user_id,
                operation="execute",
                subject_user_id=request.user_id,
                outcome="succeeded",
                scope="tenant",
                payload_json={"request_id": request.id},
            )
        )
        self.db.commit()
        return saved

    def execute_due_account_deletions(self, limit: int = 50) -> int:
        """Close every account whose pause has elapsed. Returns how many."""
        due = self.deletion_repo.list_due(utc_now(), limit=limit)
        for request in due:
            self.execute_account_deletion(request)
        return len(due)

    def _log_deletion_audit(
        self,
        ctx: RequestContext,
        request: AccountDeletionRequest,
        *,
        operation: str,
    ) -> None:
        self.db.add(
            AuditEvent(
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                event_type="identity.account.closure_requested",
                resource_type="account_deletion_request",
                resource_id=request.id,
                operation=operation,
                actor_user_id=ctx.user_id,
                subject_user_id=request.user_id,
                outcome="succeeded",
                scope="tenant",
                payload_json={
                    "operation": operation,
                    "execute_after": request.execute_after.isoformat(),
                },
            )
        )
        self.db.commit()

    # ------------------------------------------------------------------
    # Mail-backed flows: reset, verification, invitations
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def mail_is_available(self) -> bool:
        """Whether the instance can send its own mail at all."""
        return self.mail_port is not None

    async def _send_mail(self, *, to: str, subject: str, body: str, kind: str) -> None:
        if self.mail_port is None:
            raise ValidationError("This deployment cannot send mail")
        await self.mail_port.send(
            MailMessage(to=to, subject=subject, body=body, kind=kind)
        )

    def _issue_identity_token(self, user_id: str, purpose: str, ttl_minutes: int) -> str:
        """Mint a single-use link secret, retiring any earlier one."""
        self.token_repo.supersede_pending(user_id, purpose)
        raw = secrets.token_urlsafe(32)
        self.token_repo.save(
            IdentityToken(
                user_id=user_id,
                purpose=purpose,
                token_hash=self._hash_token(raw),
                expires_at=utc_now() + timedelta(minutes=ttl_minutes),
            )
        )
        return raw

    def _consume_identity_token(self, token: str, purpose: str) -> User:
        """Spend a link secret and return whose it was."""
        record = self.token_repo.get_by_hash(self._hash_token(token))
        if record is None or record.purpose != purpose or record.status != "pending":
            raise UnauthorizedError("That link is not valid")
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= utc_now():
            raise UnauthorizedError("That link has expired")

        user = self.user_repo.get_by_id(record.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("That link is not valid")

        record.status = "used"
        record.used_at = utc_now()
        self.token_repo.save(record)
        return user

    async def request_password_reset(self, email: str, link_base: str) -> None:
        """Mail a reset link, if that address belongs to an active account.

        Returns nothing either way. Telling the caller whether the address is
        registered turns this endpoint into a way to enumerate accounts, and a
        reset form is exactly where someone would try.
        """
        if self.mail_port is None:
            raise ValidationError("This deployment cannot send mail")

        user = self.user_repo.get_by_email(email)
        if user is None or not user.is_active:
            return

        token = self._issue_identity_token(user.id, "password_reset", PASSWORD_RESET_MINUTES)
        link = f"{link_base.rstrip('/')}/reset-password?token={token}"
        try:
            await self._send_mail(
                to=user.email,
                subject="Reset your SOIT password",
                body=(
                    "Someone asked to reset the password for this SOIT account.\n\n"
                    f"{link}\n\n"
                    f"The link works once and expires in {PASSWORD_RESET_MINUTES} minutes. "
                    "If this was not you, nothing has changed and you can ignore it."
                ),
                kind="password_reset",
            )
        except Exception:
            # Recorded, not raised: the caller must not learn from a failure
            # that the address exists.
            logger.exception("Failed to send a password reset mail")

    def complete_password_reset(self, token: str, new_password: str) -> User:
        """Set a new password from a reset link, and end every open session.

        Sessions end because a reset is what someone does when they think the
        account is compromised; leaving the intruder's session alive would make
        the reset pointless.
        """
        user = self._consume_identity_token(token, "password_reset")
        user.password_hash = pwd_context.hash(new_password)
        user.updated_at = utc_now()
        self.user_repo.update(user)
        for session in self.session_repo.list_by_user(user.id):
            self._end_session(session, revoked_by="password_reset")
        return user

    async def request_email_verification(self, ctx: RequestContext, link_base: str) -> None:
        """Mail the caller a link proving they control their address."""
        user = self.user_repo.get_by_id(ctx.user_id)
        if user is None:
            raise NotFoundError("User not found")
        token = self._issue_identity_token(
            user.id, "email_verification", EMAIL_VERIFICATION_MINUTES
        )
        link = f"{link_base.rstrip('/')}/verify-email?token={token}"
        await self._send_mail(
            to=user.email,
            subject="Confirm your SOIT email address",
            body=(
                "Confirm this address so SOIT can reach you about your account.\n\n"
                f"{link}\n\n"
                "The link works once."
            ),
            kind="email_verification",
        )

    def confirm_email_verification(self, token: str) -> User:
        """Mark an address confirmed."""
        user = self._consume_identity_token(token, "email_verification")
        profile = dict(user.profile_json or {})
        profile["email_verified_at"] = utc_now().isoformat()
        user.profile_json = profile
        user.updated_at = utc_now()
        return self.user_repo.update(user)

    async def invite_member(
        self,
        ctx: RequestContext,
        workspace_id: str,
        email: str,
        role: str,
        link_base: str,
    ) -> WorkspaceInvitation:
        """Offer membership to an address, whether or not it has an account."""
        if role not in WORKSPACE_ROLES:
            raise ValidationError("Invalid workspace role")
        if self.mail_port is None:
            raise ValidationError("This deployment cannot send mail")

        normalized = (email or "").strip().lower()
        if not normalized:
            raise ValidationError("An email address is required")

        existing = self.invitation_repo.get_pending_for_email(workspace_id, normalized)
        if existing is not None:
            # Re-inviting resends rather than stacking pending offers, so a
            # second click does not leave two live links.
            invitation = existing
            raw = secrets.token_urlsafe(32)
            invitation.token_hash = self._hash_token(raw)
            invitation.role = role
            invitation.expires_at = utc_now() + timedelta(days=INVITATION_DAYS)
            invitation.updated_at = utc_now()
            self.invitation_repo.save(invitation)
        else:
            raw = secrets.token_urlsafe(32)
            invitation = self.invitation_repo.save(
                WorkspaceInvitation(
                    tenant_id=ctx.tenant_id,
                    workspace_id=workspace_id,
                    email=normalized,
                    role=role,
                    token_hash=self._hash_token(raw),
                    invited_by=ctx.user_id,
                    expires_at=utc_now() + timedelta(days=INVITATION_DAYS),
                )
            )

        link = f"{link_base.rstrip('/')}/accept-invitation?token={raw}"
        await self._send_mail(
            to=normalized,
            subject="You have been invited to a SOIT workspace",
            body=(
                "You have been invited to join a workspace in SOIT.\n\n"
                f"{link}\n\n"
                f"The invitation expires in {INVITATION_DAYS} days."
            ),
            kind="invitation",
        )
        return invitation

    def list_invitations(self, workspace_id: str) -> list[WorkspaceInvitation]:
        """Pending offers for a workspace."""
        return self.invitation_repo.list_for_workspace(workspace_id)

    def revoke_invitation(self, ctx: RequestContext, invitation_id: str) -> WorkspaceInvitation:
        """Withdraw an offer before it is accepted."""
        invitation = self.invitation_repo.get_by_id(invitation_id)
        if invitation is None or invitation.workspace_id != ctx.workspace_id:
            raise NotFoundError("Invitation not found")
        if invitation.status != "pending":
            return invitation
        invitation.status = "revoked"
        invitation.revoked_at = utc_now()
        invitation.updated_at = utc_now()
        # The link stops working immediately, not when it expires.
        invitation.token_hash = f"revoked:{invitation.id}:{secrets.token_hex(8)}"
        return self.invitation_repo.save(invitation)

    def accept_invitation(self, token: str, user_id: str) -> WorkspaceInvitation:
        """Redeem an invitation for an existing account."""
        invitation = self.invitation_repo.get_by_hash(self._hash_token(token))
        if invitation is None or invitation.status != "pending":
            raise UnauthorizedError("That invitation is not valid")
        expires_at = invitation.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= utc_now():
            raise UnauthorizedError("That invitation has expired")

        user = self.user_repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("That invitation is not valid")
        if (user.email or "").strip().lower() != invitation.email:
            # The offer was addressed to one person. Redeeming it as another
            # would let a forwarded link move membership to whoever opened it.
            raise ForbiddenError("This invitation was sent to a different address")

        ctx = RequestContext(
            tenant_id=invitation.tenant_id,
            workspace_id=invitation.workspace_id,
            user_id=user_id,
        )
        if self.tenant_membership_repo.get(invitation.tenant_id, user_id) is None:
            self.tenant_membership_repo.create(
                TenantMembership(
                    tenant_id=invitation.tenant_id,
                    user_id=user_id,
                    role=TENANT_ROLE_DEV,
                )
            )
        membership_repo = self.workspace_membership_repo_factory(ctx)
        if membership_repo.get(invitation.workspace_id, user_id) is None:
            membership_repo.create(
                WorkspaceMembership(
                    workspace_id=invitation.workspace_id,
                    user_id=user_id,
                    role=invitation.role,
                )
            )

        invitation.status = "accepted"
        invitation.accepted_at = utc_now()
        invitation.accepted_user_id = user_id
        invitation.updated_at = utc_now()
        invitation.token_hash = f"accepted:{invitation.id}:{secrets.token_hex(8)}"
        return self.invitation_repo.save(invitation)

    # ------------------------------------------------------------------
    # Second factor
    # ------------------------------------------------------------------

    @staticmethod
    def _app_secret() -> str:
        from app.settings.settings import settings

        return settings.secret_key

    def get_mfa(self, user_id: str) -> UserMfa | None:
        """Return the user's enrolment, pending or active."""
        return self.mfa_repo.get_by_user(user_id)

    def mfa_is_active(self, user_id: str) -> bool:
        """Whether this user has a confirmed second factor."""
        enrolment = self.mfa_repo.get_by_user(user_id)
        return enrolment is not None and enrolment.status == "active"

    def start_mfa_enrolment(
        self,
        ctx: RequestContext,
        issuer: str = "SOIT",
    ) -> tuple[str, str]:
        """Begin enrolment and return (secret, provisioning URI).

        Restarting replaces a pending enrolment: a half-finished scan is not
        worth protecting, and refusing would strand someone holding a secret
        their authenticator never received. An active enrolment is never
        replaced -- turning the second factor off is a separate, deliberate act.
        """
        existing = self.mfa_repo.get_by_user(ctx.user_id)
        if existing is not None and existing.status == "active":
            raise ValidationError("Two-factor authentication is already enabled")

        secret = totp.generate_secret()
        sealed = sealing.seal(secret, secret_key=self._app_secret())
        if existing is not None:
            existing.secret_sealed = sealed
            existing.status = "pending"
            existing.recovery_hashes_json = []
            existing.updated_at = utc_now()
            self.mfa_repo.save(existing)
        else:
            self.mfa_repo.save(
                UserMfa(user_id=ctx.user_id, secret_sealed=sealed, status="pending")
            )

        user = self.user_repo.get_by_id(ctx.user_id)
        account = user.email if user else ctx.user_id
        return secret, totp.provisioning_uri(secret, account=account, issuer=issuer)

    def confirm_mfa_enrolment(self, ctx: RequestContext, code: str) -> list[str]:
        """Activate enrolment once a code proves the authenticator holds it.

        Activating at setup instead would let a mistyped scan lock someone out
        of their own account. Returns the recovery codes, shown once and stored
        only as hashes.
        """
        enrolment = self.mfa_repo.get_by_user(ctx.user_id)
        if enrolment is None:
            raise NotFoundError("No enrolment in progress")
        if enrolment.status == "active":
            raise ValidationError("Two-factor authentication is already enabled")

        secret = sealing.unseal(enrolment.secret_sealed, secret_key=self._app_secret())
        if not totp.verify_code(secret, code, int(utc_now().timestamp())):
            raise UnauthorizedError("That code is not valid")

        codes = totp.generate_recovery_codes()
        enrolment.status = "active"
        enrolment.confirmed_at = utc_now()
        enrolment.recovery_hashes_json = [
            totp.hash_recovery_code(item) for item in codes
        ]
        enrolment.updated_at = utc_now()
        self.mfa_repo.save(enrolment)
        self._log_mfa_audit(ctx, operation="enable")
        return codes

    def disable_mfa(self, ctx: RequestContext, password: str) -> None:
        """Turn the second factor off, after proving the password.

        An unlocked laptop is exactly the situation a second factor exists for,
        so a live session alone must not be enough to drop it.
        """
        user = self.user_repo.get_by_id(ctx.user_id)
        if user is None or not pwd_context.verify(password, user.password_hash):
            raise UnauthorizedError("Password is incorrect")
        enrolment = self.mfa_repo.get_by_user(ctx.user_id)
        if enrolment is None:
            return
        self.mfa_repo.delete(enrolment)
        self._log_mfa_audit(ctx, operation="disable")

    def regenerate_recovery_codes(self, ctx: RequestContext, code: str) -> list[str]:
        """Replace the recovery codes, proving possession of the authenticator."""
        enrolment = self.mfa_repo.get_by_user(ctx.user_id)
        if enrolment is None or enrolment.status != "active":
            raise NotFoundError("Two-factor authentication is not enabled")
        secret = sealing.unseal(enrolment.secret_sealed, secret_key=self._app_secret())
        if not totp.verify_code(secret, code, int(utc_now().timestamp())):
            raise UnauthorizedError("That code is not valid")

        codes = totp.generate_recovery_codes()
        enrolment.recovery_hashes_json = [
            totp.hash_recovery_code(item) for item in codes
        ]
        enrolment.updated_at = utc_now()
        self.mfa_repo.save(enrolment)
        self._log_mfa_audit(ctx, operation="recovery_codes_regenerated")
        return codes

    def _verify_second_factor(self, user_id: str, code: str) -> bool:
        """Accept an authenticator code, or spend a recovery code."""
        enrolment = self.mfa_repo.get_by_user(user_id)
        if enrolment is None or enrolment.status != "active":
            return False

        secret = sealing.unseal(enrolment.secret_sealed, secret_key=self._app_secret())
        if totp.verify_code(secret, code, int(utc_now().timestamp())):
            enrolment.last_used_at = utc_now()
            self.mfa_repo.save(enrolment)
            return True

        # Recovery codes are single use: matching one strikes it off, so a
        # printed sheet is worth as many sign-ins as it has lines left.
        candidate = totp.hash_recovery_code(code)
        remaining = list(enrolment.recovery_hashes_json or [])
        if candidate in remaining:
            remaining.remove(candidate)
            enrolment.recovery_hashes_json = remaining
            enrolment.last_used_at = utc_now()
            enrolment.updated_at = utc_now()
            self.mfa_repo.save(enrolment)
            return True
        return False

    def _log_mfa_audit(self, ctx: RequestContext, *, operation: str) -> None:
        self.db.add(
            AuditEvent(
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                event_type="identity.mfa.changed",
                resource_type="user_mfa",
                resource_id=ctx.user_id,
                operation=operation,
                actor_user_id=ctx.user_id,
                subject_user_id=ctx.user_id,
                outcome="succeeded",
                scope="tenant",
                payload_json={"operation": operation},
            )
        )
        self.db.commit()

    def _issue_mfa_challenge(self, user_id: str, tenant_id: str) -> str:
        """Mint the short-lived token that stands between password and session.

        It is a JWT so nothing has to be stored for it, and it carries a claim
        marking it as a challenge: an access token and a challenge token must
        never be interchangeable, or the second factor would be optional for
        anyone who noticed.
        """
        return self.jwt_manager.create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            expires_delta=timedelta(minutes=MFA_CHALLENGE_MINUTES),
            purpose=MFA_CHALLENGE_PURPOSE,
        )

    def complete_mfa_login(
        self,
        challenge_token: str,
        code: str,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[User, str, str, str]:
        """Finish a sign-in that stopped at the second factor.

        Returns:
            Tuple of (User, access_token, workspace_id, refresh_token).
        """
        payload = self.jwt_manager.decode_token(challenge_token)
        if payload.get("purpose") != MFA_CHALLENGE_PURPOSE:
            raise UnauthorizedError("That token cannot complete a sign-in")

        user_id = str(payload.get("sub") or "")
        tenant_id = str(payload.get("tenant_id") or "")
        if not user_id or not tenant_id:
            raise UnauthorizedError("Challenge is missing required claims")

        user = self.user_repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("User account is inactive")
        if not self._verify_second_factor(user_id, code):
            raise UnauthorizedError("That code is not valid")

        membership = next(
            (
                item
                for item in self.tenant_membership_repo.get_by_user(user_id)
                if item.tenant_id == tenant_id
            ),
            None,
        )
        if membership is None:
            raise UnauthorizedError("User has no tenant membership")

        workspace_id, workspace_role = self._ensure_workspace_membership(
            tenant_id=tenant_id,
            user_id=user_id,
            tenant_role=membership.role,
        )
        session, refresh_token = self._issue_session(
            user_id=user_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        access_token = self.jwt_manager.create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            tenant_role=membership.role,
            workspace_role=workspace_role,
            session_id=session.id,
        )
        return user, access_token, workspace_id, refresh_token

    # ------------------------------------------------------------------
    # Personal shortcuts: kept filters and pinned objects
    # ------------------------------------------------------------------

    def list_saved_views(self, ctx: RequestContext, surface: str | None = None) -> list[SavedView]:
        """List the caller's kept filters, optionally for one screen."""
        return self.saved_view_repo_factory(ctx).list(surface)

    def create_saved_view(self, ctx: RequestContext, data: SavedViewCreate) -> SavedView:
        """Keep a filter under a name, replacing one of the same name."""
        repo = self.saved_view_repo_factory(ctx)
        existing = repo.get_by_name(data.surface, data.name)
        if existing is not None:
            # Saving over a name is how a person updates a view; refusing would
            # make them delete and recreate to change one filter.
            existing.query = data.query
            existing.is_default = data.is_default
            existing.updated_at = utc_now()
            view = repo.save(existing)
        else:
            view = repo.save(
                SavedView(
                    tenant_id=ctx.tenant_id,
                    workspace_id=ctx.workspace_id,
                    user_id=ctx.user_id,
                    surface=data.surface,
                    name=data.name,
                    query=data.query,
                    is_default=data.is_default,
                )
            )
        if view.is_default:
            repo.clear_default(view.surface, except_id=view.id)
        return view

    def update_saved_view(
        self,
        ctx: RequestContext,
        view_id: str,
        data: SavedViewUpdate,
    ) -> SavedView:
        """Rename a kept filter, repoint it, or make it the default."""
        repo = self.saved_view_repo_factory(ctx)
        view = repo.get(view_id)
        if view is None:
            raise NotFoundError("Saved view not found")
        if data.name is not None:
            view.name = data.name
        if data.query is not None:
            view.query = data.query
        if data.is_default is not None:
            view.is_default = data.is_default
        view.updated_at = utc_now()
        saved = repo.save(view)
        if saved.is_default:
            repo.clear_default(saved.surface, except_id=saved.id)
        return saved

    def delete_saved_view(self, ctx: RequestContext, view_id: str) -> None:
        """Drop one of the caller's kept filters."""
        repo = self.saved_view_repo_factory(ctx)
        view = repo.get(view_id)
        if view is None:
            raise NotFoundError("Saved view not found")
        repo.delete(view)

    def list_pins(self, ctx: RequestContext) -> list[PinnedObject]:
        """List the caller's pinned objects, most recent first."""
        return self.pin_repo_factory(ctx).list()

    def create_pin(self, ctx: RequestContext, data: PinCreate) -> PinnedObject:
        """Pin an object, or return the existing pin unchanged."""
        repo = self.pin_repo_factory(ctx)
        existing = repo.get_by_target(data.object_type, data.object_id)
        if existing is not None:
            return existing
        return repo.save(
            PinnedObject(
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                user_id=ctx.user_id,
                object_type=data.object_type,
                object_id=data.object_id,
                label=data.label,
            )
        )

    def delete_pin(self, ctx: RequestContext, pin_id: str) -> None:
        """Unpin an object."""
        repo = self.pin_repo_factory(ctx)
        pin = repo.get(pin_id)
        if pin is None:
            raise NotFoundError("Pin not found")
        repo.delete(pin)

    def create_tenant(
        self,
        tenant_data: TenantCreate,
        user_id: str,
    ) -> Tenant:
        """Create a new tenant.

        Args:
            tenant_data: Tenant creation data.
            user_id: User ID of the creator (becomes owner).

        Returns:
            Created Tenant instance.
        """
        # Check if tenant name already exists
        existing = self.tenant_repo.get_by_name(tenant_data.name)
        if existing:
            raise ValidationError("Tenant with this name already exists")

        # Create tenant
        tenant = Tenant(
            name=tenant_data.name,
            plan=tenant_data.plan,
        )
        tenant = self.tenant_repo.create(tenant)

        # Create owner membership
        membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=user_id,
            role=TENANT_ROLE_OWNER,
        )
        self.tenant_membership_repo.create(membership)

        return tenant

    def create_workspace(
        self,
        workspace_data: WorkspaceCreate,
        ctx: RequestContext,
    ) -> Workspace:
        """Create a new workspace.

        Args:
            workspace_data: Workspace creation data.
            ctx: Request context.

        Returns:
            Created Workspace instance.
        """
        workspace_repo = self.workspace_repo_factory(ctx)

        # Check if workspace name already exists in tenant
        existing = workspace_repo.get_by_name(workspace_data.name)
        if existing:
            raise ValidationError("Workspace with this name already exists")

        # Create workspace
        workspace = Workspace(
            tenant_id=ctx.tenant_id,
            name=workspace_data.name,
            description=workspace_data.description,
        )
        workspace = workspace_repo.create(workspace)

        # Create owner membership
        membership_repo = self.workspace_membership_repo_factory(ctx)
        membership = WorkspaceMembership(
            tenant_id=ctx.tenant_id,
            workspace_id=workspace.id,
            user_id=ctx.user_id,
            role=WORKSPACE_ROLE_OWNER,
        )
        membership_repo.create(membership)

        return workspace

    def add_tenant_member(
        self,
        tenant_id: str,
        membership_data: MembershipCreate,
        ctx: RequestContext,
    ) -> TenantMembership:
        """Add a member to a tenant.

        Args:
            tenant_id: Tenant ID.
            membership_data: Membership creation data.
            ctx: Request context.

        Returns:
            Created TenantMembership instance.

        Raises:
            ForbiddenError: If user doesn't have permission.
            NotFoundError: If tenant or user not found.
        """
        # Check permission (only tenant admin/owner can add members)
        if ctx.tenant_id != tenant_id:
            raise ValidationError("Cannot add members to different tenant")

        if not ctx.is_tenant_admin():
            raise ValidationError("Tenant admin role required")

        # Verify tenant exists
        tenant = self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundError("Tenant not found")

        # Verify user exists
        user = self.user_repo.get_by_id(membership_data.user_id)
        if not user:
            raise NotFoundError("User not found")

        if membership_data.role not in TENANT_ROLES:
            raise ValidationError("Invalid tenant role")

        # Check if membership already exists
        existing = self.tenant_membership_repo.get(tenant_id, membership_data.user_id)
        if existing:
            raise ValidationError("User is already a member of this tenant")

        # Create membership
        membership = TenantMembership(
            tenant_id=tenant_id,
            user_id=membership_data.user_id,
            role=membership_data.role,
        )
        return self.tenant_membership_repo.create(membership)

    def add_workspace_member(
        self,
        workspace_id: str,
        membership_data: MembershipCreate,
        ctx: RequestContext,
    ) -> WorkspaceMembership:
        """Add a member to a workspace.

        Args:
            workspace_id: Workspace ID.
            membership_data: Membership creation data.
            ctx: Request context.

        Returns:
            Created WorkspaceMembership instance.

        Raises:
            ForbiddenError: If user doesn't have permission.
            NotFoundError: If workspace or user not found.
        """
        # Check permission (only workspace owner/maintainer can add members)
        workspace_repo = self.workspace_repo_factory(ctx)
        workspace = workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")

        if not ctx.can_write():
            raise ValidationError("Workspace write permission required")

        # Verify user exists
        user = self.user_repo.get_by_id(membership_data.user_id)
        if not user:
            raise NotFoundError("User not found")

        # Verify user is member of tenant
        tenant_membership = self.tenant_membership_repo.get(ctx.tenant_id, membership_data.user_id)
        if not tenant_membership:
            raise ValidationError("User must be a member of the tenant first")

        if membership_data.role not in WORKSPACE_ROLES:
            raise ValidationError("Invalid workspace role")

        # Check if membership already exists
        membership_repo = self.workspace_membership_repo_factory(ctx)
        existing = membership_repo.get(workspace_id, membership_data.user_id)
        if existing:
            raise ValidationError("User is already a member of this workspace")

        # Create membership
        membership = WorkspaceMembership(
            tenant_id=ctx.tenant_id,
            workspace_id=workspace_id,
            user_id=membership_data.user_id,
            role=membership_data.role,
        )
        return membership_repo.create(membership)

    def get_user(self, user_id: str) -> User:
        """Get user by id."""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User not found: {user_id}")
        return user

    def update_user_profile(
        self,
        ctx: RequestContext,
        data: UserProfileUpdate,
    ) -> User:
        """Update current user profile."""
        user = self.get_user(ctx.user_id)
        if data.email and data.email != user.email:
            existing = self.user_repo.get_by_email(data.email)
            if existing and existing.id != user.id:
                raise ValidationError("User with this email already exists")
            user.email = data.email
        if data.name is not None:
            user.name = data.name
        if data.profile is not None:
            profile = dict(getattr(user, "profile_json", {}) or {})
            profile.update(data.profile)
            user.profile_json = profile
        user.updated_at = utc_now()
        return self.user_repo.update(user)

    def change_password(
        self,
        ctx: RequestContext,
        data: PasswordChange,
    ) -> None:
        """Change current user password."""
        user = self.get_user(ctx.user_id)
        if not pwd_context.verify(data.current_password, user.password_hash):
            raise UnauthorizedError("Current password is incorrect")
        user.password_hash = pwd_context.hash(data.new_password)
        user.updated_at = utc_now()
        self.user_repo.update(user)

    def get_tenant(self, tenant_id: str) -> Tenant:
        """Get tenant by id."""
        tenant = self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise NotFoundError(f"Tenant not found: {tenant_id}")
        return tenant

    def list_workspaces(self, *, tenant_id: str, ctx: RequestContext) -> list[Workspace]:
        """List workspaces in a tenant."""
        if ctx.tenant_id != tenant_id:
            raise ValidationError("tenant_id mismatch with current context")
        repo = self.workspace_repo_factory(ctx)
        return repo.list_by_tenant()

    def get_workspace(self, *, workspace_id: str, ctx: RequestContext) -> Workspace:
        """Get workspace by id (ctx scoped)."""
        repo = self.workspace_repo_factory(ctx)
        workspace = repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(f"Workspace not found: {workspace_id}")
        return workspace

    def update_workspace(
        self,
        workspace_id: str,
        ctx: RequestContext,
        data: WorkspaceUpdate,
    ) -> Workspace:
        """Update workspace metadata."""
        if not ctx.can_write():
            raise ValidationError("Workspace write permission required")
        repo = self.workspace_repo_factory(ctx)
        workspace = repo.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(f"Workspace not found: {workspace_id}")
        if data.name:
            workspace.name = data.name
        if data.description is not None:
            workspace.description = data.description
        if data.metadata is not None:
            metadata = dict(getattr(workspace, "metadata_json", {}) or {})
            metadata.update(data.metadata)
            workspace.metadata_json = metadata
        quota_fields = (
            "llm_rate_limit_per_minute",
            "tool_rate_limit_per_minute",
            "llm_daily_quota",
            "tool_daily_quota",
        )
        # Explicit null clears the workspace override so the tenant-level value applies.
        provided_quota_fields = [
            field for field in quota_fields if field in data.model_fields_set
        ]
        if provided_quota_fields:
            if not ctx.is_tenant_admin():
                raise ValidationError("Tenant admin role required to change workspace quotas")
            for field in provided_quota_fields:
                setattr(workspace, field, getattr(data, field))
        if "require_mfa" in data.model_fields_set and data.require_mfa is not None:
            # A workspace-wide security requirement, not a personal preference:
            # the same bar as changing quotas.
            if not ctx.is_tenant_admin():
                raise ValidationError(
                    "Tenant admin role required to change the workspace MFA requirement"
                )
            workspace.require_mfa = bool(data.require_mfa)
        workspace.updated_at = utc_now()
        return repo.update(workspace)

    def get_user_workspace_role(
        self,
        workspace_id: str,
        user_id: str,
        ctx: RequestContext,
    ) -> str | None:
        """Get user's role in a workspace."""
        membership_repo = self.workspace_membership_repo_factory(ctx)
        membership = membership_repo.get(workspace_id, user_id)
        return membership.role if membership else None

    def list_workspace_members(
        self,
        workspace_id: str,
        ctx: RequestContext,
    ) -> list[WorkspaceMembership]:
        """List workspace members."""
        repo = self.workspace_membership_repo_factory(ctx)
        return repo.get_by_workspace(workspace_id)

    def list_my_workspaces(self, ctx: RequestContext) -> list[tuple[Workspace, str]]:
        """Return the caller's own workspaces in the current tenant, with roles.

        Distinct from ``list_workspaces``, which answers "every workspace in
        this tenant" and is an administrative question. This one is what a
        workspace switcher needs, and any member may ask it.
        """
        membership_repo = self.workspace_membership_repo_factory(ctx)
        workspace_repo = self.workspace_repo_factory(ctx)
        pairs: list[tuple[Workspace, str]] = []
        for membership in membership_repo.get_by_user(ctx.user_id):
            workspace = workspace_repo.get_by_id(membership.workspace_id)
            # A membership can outlive the workspace it points at; showing a
            # dangling row in a switcher would offer a destination that 404s.
            if workspace is None or workspace.tenant_id != ctx.tenant_id:
                continue
            pairs.append((workspace, membership.role))
        pairs.sort(key=lambda pair: pair[0].created_at)
        return pairs

    def update_workspace_member_role(
        self,
        workspace_id: str,
        user_id: str,
        role: str,
        ctx: RequestContext,
    ) -> WorkspaceMembership:
        """Update workspace member role."""
        if role not in WORKSPACE_ROLES:
            raise ValidationError("Invalid workspace role")
        repo = self.workspace_membership_repo_factory(ctx)
        membership = repo.get(workspace_id, user_id)
        if not membership:
            raise NotFoundError("Workspace membership not found")
        membership.role = role
        return repo.update(membership)

    def remove_workspace_member(
        self,
        workspace_id: str,
        user_id: str,
        ctx: RequestContext,
    ) -> None:
        """Remove a member from workspace."""
        if user_id == ctx.user_id:
            raise ValidationError("Cannot remove yourself from the workspace")
        repo = self.workspace_membership_repo_factory(ctx)
        deleted = repo.delete(workspace_id, user_id)
        if not deleted:
            raise NotFoundError("Workspace membership not found")

    def get_user_tenant_role(
        self,
        tenant_id: str,
        user_id: str,
    ) -> str | None:
        """Get user's role in a tenant."""
        membership = self.tenant_membership_repo.get(tenant_id, user_id)
        return membership.role if membership else None

    def create_api_key(
        self,
        data: ApiKeyCreate,
        ctx: RequestContext,
    ) -> tuple[ApiKey, str]:
        """Create API key and return plaintext key once."""
        import hashlib
        import secrets

        raw_key = f"sk_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        key_prefix = raw_key[:12]

        api_key = ApiKey(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            name=data.name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            status="active",
            scopes_json=sorted(normalize_scopes(data.scopes)),
            expires_at=utc_now() + timedelta(days=data.expires_in_days),
        )
        api_key = self.api_key_repo.create(api_key)
        return api_key, raw_key

    def list_api_keys(
        self,
        ctx: RequestContext,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ApiKey]:
        """List API keys for workspace."""
        return self.api_key_repo.list_by_workspace(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            limit=limit,
            offset=offset,
        )

    def revoke_api_key(
        self,
        key_id: str,
        ctx: RequestContext,
    ) -> ApiKey:
        """Revoke an API key."""
        api_key = self.api_key_repo.get_by_id(key_id)
        if not api_key:
            raise NotFoundError(f"API key not found: {key_id}")
        if api_key.tenant_id != ctx.tenant_id or api_key.workspace_id != ctx.workspace_id:
            raise ValidationError("API key scope mismatch")
        api_key.status = "revoked"
        api_key.revoked_at = utc_now()
        api_key.updated_at = utc_now()
        return self.api_key_repo.update(api_key)

    def rotate_api_key(
        self,
        key_id: str,
        ctx: RequestContext,
    ) -> tuple[ApiKey, str]:
        """Rotate an API key by revoking and issuing a new one."""
        old_key = self.api_key_repo.get_by_id(key_id)
        if not old_key:
            raise NotFoundError(f"API key not found: {key_id}")
        if old_key.tenant_id != ctx.tenant_id or old_key.workspace_id != ctx.workspace_id:
            raise ValidationError("API key scope mismatch")

        old_key.status = "revoked"
        old_key.revoked_at = utc_now()
        old_key.updated_at = utc_now()
        self.api_key_repo.update(old_key)

        # Rotation replaces the secret, not the grant: carry the scopes over and
        # restart the same lifetime rather than silently widening either.
        remaining_days = 1
        if old_key.expires_at is not None:
            remaining_days = max(
                1, (old_key.expires_at - old_key.created_at).days or 1
            )
        new_key_data = ApiKeyCreate(
            name=old_key.name,
            scopes=list(old_key.scopes_json or []),
            expires_in_days=min(365, remaining_days),
        )
        return self.create_api_key(new_key_data, ctx)

    def create_resource_grant(
        self,
        data: ResourceGrantCreate,
        ctx: RequestContext,
    ) -> ResourceGrant:
        """Create or update a resource grant."""
        if not ctx.can_write():
            raise ValidationError("Workspace write permission required")

        if not data.actions:
            raise ValidationError("At least one action is required")

        actions = self._normalize_actions(data.actions)
        if not actions:
            raise ValidationError("At least one action is required")

        grant_repo = self.resource_grant_repo_factory(ctx)
        existing = grant_repo.get_by_resource_user(
            data.resource_type,
            data.resource_id,
            data.user_id,
        )

        if existing:
            existing.actions = actions
            existing.updated_at = utc_now()
            grant = grant_repo.update(existing)
            operation = "update"
        else:
            grant = grant_repo.create(
                ResourceGrant(
                    resource_type=data.resource_type,
                    resource_id=data.resource_id,
                    user_id=data.user_id,
                    actions=actions,
                    created_by=ctx.user_id,
                )
            )
            operation = "grant"

        self._log_resource_grant_audit(
            ctx=ctx,
            resource_type=data.resource_type,
            resource_id=data.resource_id,
            user_id=data.user_id,
            actions=actions,
            operation=operation,
        )
        self._invalidate_permission_cache(
            ctx,
            data.resource_type,
            data.resource_id,
            data.user_id,
        )
        return grant

    def revoke_resource_grant(
        self,
        resource_type: str,
        resource_id: str,
        user_id: str,
        ctx: RequestContext,
    ) -> None:
        """Revoke a resource grant."""
        if not ctx.can_write():
            raise ValidationError("Workspace write permission required")

        grant_repo = self.resource_grant_repo_factory(ctx)
        deleted = grant_repo.delete_by_resource_user(resource_type, resource_id, user_id)
        if not deleted:
            raise NotFoundError("Resource grant not found")

        self._log_resource_grant_audit(
            ctx=ctx,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            actions=[],
            operation="revoke",
        )
        self._invalidate_permission_cache(ctx, resource_type, resource_id, user_id)

    def list_resource_grants(
        self,
        resource_type: str | None,
        resource_id: str | None,
        ctx: RequestContext,
        *,
        limit: int = 500,
    ) -> list[ResourceGrant]:
        """List resource grants, for one resource or across the workspace.

        Naming a resource returns its grants. Omitting the resource id returns
        every grant in the workspace, optionally narrowed to one resource type,
        so the access surface can be answered in a single call instead of a
        request per object.
        """
        grant_repo = self.resource_grant_repo_factory(ctx)
        if resource_type and resource_id:
            return grant_repo.list_by_resource(resource_type, resource_id)
        return grant_repo.list_in_scope(resource_type=resource_type, limit=limit)

    def _invalidate_permission_cache(
        self,
        ctx: RequestContext,
        resource_type: str,
        resource_id: str,
        user_id: str,
    ) -> None:
        from app.kernel.identity.permissions import get_permission_cache

        cache = get_permission_cache()
        self._run_async(
            cache.invalidate_permission(
                ctx=ctx,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
            )
        )

    def _log_resource_grant_audit(
        self,
        *,
        ctx: RequestContext,
        resource_type: str,
        resource_id: str,
        user_id: str,
        actions: list[str],
        operation: str,
    ) -> None:
        """Record a resource grant audit entry."""
        audit = AuditEvent(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            event_type="identity.resource_grant.changed",
            resource_type=resource_type,
            resource_id=resource_id,
            operation=operation,
            actor_user_id=ctx.user_id,
            subject_user_id=user_id,
            scope="workspace",
            payload_json={"actions": actions},
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(audit)
