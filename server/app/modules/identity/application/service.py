""" service

Identity domain business logic.
"""

import asyncio
import threading
from collections.abc import Callable
from datetime import timedelta

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError, UnauthorizedError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
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
from app.kernel.runtime.db.models.audit import AuditEvent
from app.modules.identity.application.ports import (
    ApiKeyRepositoryPort,
    ResourceGrantRepositoryPort,
    TenantMembershipRepositoryPort,
    TenantRepositoryPort,
    UserRepositoryPort,
    WorkspaceMembershipRepositoryPort,
    WorkspaceRepositoryPort,
)
from app.modules.identity.application.schemas import (
    ApiKeyCreate,
    MembershipCreate,
    PasswordChange,
    ResourceGrantCreate,
    TenantCreate,
    UserCreate,
    UserProfileUpdate,
    WorkspaceCreate,
    WorkspaceUpdate,
)
from app.modules.identity.domain.models import (
    ApiKey,
    ResourceGrant,
    Tenant,
    TenantMembership,
    User,
    Workspace,
    WorkspaceMembership,
)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
    ) -> tuple[User, Tenant, str, str]:
        """Register a new user and create a tenant.

        Args:
            user_data: User creation data.
            tenant_name: Optional tenant name (creates tenant if provided).

        Returns:
            Tuple of (User, Tenant, access_token, workspace_id).

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

        # Generate access token
        access_token = self.jwt_manager.create_access_token(
            user_id=user.id,
            tenant_id=tenant.id,
            workspace_id=workspace_id,
            tenant_role=TENANT_ROLE_OWNER,
            workspace_role=workspace_role,
        )

        return user, tenant, access_token, workspace_id

    def authenticate_user(
        self,
        email: str,
        password: str,
    ) -> tuple[User, str, str]:
        """Authenticate a user.

        Args:
            email: User email.
            password: User password.

        Returns:
            Tuple of (User, access_token, workspace_id).

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

        workspace_id, workspace_role = self._ensure_workspace_membership(
            tenant_id=tenant_id,
            user_id=user.id,
            tenant_role=tenant_role,
        )

        # Generate access token
        access_token = self.jwt_manager.create_access_token(
            user_id=user.id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            tenant_role=tenant_role,
            workspace_role=workspace_role,
        )

        return user, access_token, workspace_id

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
