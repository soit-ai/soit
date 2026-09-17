""" repository

Identity repositories using scope-aware base.
"""


from datetime import datetime

from sqlalchemy import and_, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.repository import AsyncRepository
from app.kernel.contracts.context import RequestContext
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


def _unwrap_result(result):
    """Unwrap SQLAlchemy row results to model instances."""
    if result is None:
        return None
    if isinstance(result, list | tuple):
        return result[0] if result else None
    if hasattr(result, "_mapping"):
        return result[0]
    return result


def _unwrap_all(results):
    """Unwrap list of SQLAlchemy rows to model instances."""
    if not results:
        return []
    first = results[0]
    if isinstance(first, list | tuple) or hasattr(first, "_mapping"):
        return [item[0] for item in results]
    return results


class UserRepository:
    """Repository for User model (global scope)."""

    def __init__(self, db: AsyncSession):
        """Initialize user repository.

        Args:
            db: Database session.
        """
        self.db = db

    async def get_by_id(self, user_id: str) -> User | None:
        """Get user by ID.

        Args:
            user_id: User ID.

        Returns:
            User instance or None if not found.
        """
        return await self.db.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email.

        Args:
            email: User email.

        Returns:
            User instance or None if not found.
        """
        query = select(User).where(User.email == email)
        result = (await self.db.exec(query)).scalars().first()
        return _unwrap_result(result)

    async def create(self, user: User) -> User:
        """Create a new user.

        Args:
            user: User instance to create.

        Returns:
            Created user instance.
        """
        self.db.add(user)
        await self.db.commit()
        return user

    async def update(self, user: User) -> User:
        """Update an existing user.

        Args:
            user: User instance to update.

        Returns:
            Updated user instance.
        """
        await self.db.commit()
        return user


class TenantRepository:
    """Repository for Tenant model (global scope)."""

    def __init__(self, db: AsyncSession):
        """Initialize tenant repository.

        Args:
            db: Database session.
        """
        self.db = db

    async def get_by_id(self, tenant_id: str) -> Tenant | None:
        """Get tenant by ID.

        Args:
            tenant_id: Tenant ID.

        Returns:
            Tenant instance or None if not found.
        """
        return await self.db.get(Tenant, tenant_id)

    async def get_by_name(self, name: str) -> Tenant | None:
        """Get tenant by name.

        Args:
            name: Tenant name.

        Returns:
            Tenant instance or None if not found.
        """
        query = select(Tenant).where(Tenant.name == name)
        result = (await self.db.exec(query)).scalars().first()
        return _unwrap_result(result)

    async def create(self, tenant: Tenant) -> Tenant:
        """Create a new tenant.

        Args:
            tenant: Tenant instance to create.

        Returns:
            Created tenant instance.
        """
        self.db.add(tenant)
        await self.db.commit()
        return tenant

    async def update(self, tenant: Tenant) -> Tenant:
        """Update an existing tenant.

        Args:
            tenant: Tenant instance to update.

        Returns:
            Updated tenant instance.
        """
        await self.db.commit()
        return tenant


class WorkspaceRepository(AsyncRepository[Workspace]):
    """Repository for Workspace model."""

    def __init__(self, db: AsyncSession, ctx: RequestContext):
        """Initialize workspace repository.

        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(Workspace, db, ctx)

    async def get_by_name(self, name: str) -> Workspace | None:
        """Get workspace by name.

        Args:
            name: Workspace name.

        Returns:
            Workspace instance or None if not found.
        """
        query = select(Workspace).where(
            and_(
                Workspace.tenant_id == self.ctx.tenant_id,
                Workspace.name == name,
            )
        )
        result = (await self.db.exec(query)).scalars().first()
        return self._unwrap_result(result)

    async def list_by_tenant(self) -> list[Workspace]:
        """List all workspaces in tenant.

        Returns:
            List of Workspace instances.
        """
        query = select(Workspace).where(
            Workspace.tenant_id == self.ctx.tenant_id
        ).order_by(Workspace.created_at.desc())
        results = list((await self.db.exec(query)).scalars().all())
        return self._unwrap_all(results)


class TenantMembershipRepository:
    """Repository for TenantMembership model."""

    def __init__(self, db: AsyncSession):
        """Initialize tenant membership repository.

        Args:
            db: Database session.
        """
        self.db = db

    async def get(self, tenant_id: str, user_id: str) -> TenantMembership | None:
        """Get membership.

        Args:
            tenant_id: Tenant ID.
            user_id: User ID.

        Returns:
            TenantMembership instance or None if not found.
        """
        return await self.db.get(TenantMembership, (tenant_id, user_id))

    async def get_by_user(self, user_id: str) -> list[TenantMembership]:
        """Get all memberships for a user.

        Args:
            user_id: User ID.

        Returns:
            List of TenantMembership instances.
        """
        query = select(TenantMembership).where(
            TenantMembership.user_id == user_id
        )
        results = list((await self.db.exec(query)).scalars().all())
        return _unwrap_all(results)

    async def get_by_tenant(self, tenant_id: str) -> list[TenantMembership]:
        """Get all memberships for a tenant.

        Args:
            tenant_id: Tenant ID.

        Returns:
            List of TenantMembership instances.
        """
        query = select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id
        )
        results = list((await self.db.exec(query)).scalars().all())
        return _unwrap_all(results)

    async def create(self, membership: TenantMembership) -> TenantMembership:
        """Create a new membership.

        Args:
            membership: Membership instance to create.

        Returns:
            Created membership instance.
        """
        self.db.add(membership)
        await self.db.commit()
        return membership

    async def update(self, membership: TenantMembership) -> TenantMembership:
        """Update an existing membership.

        Args:
            membership: Membership instance to update.

        Returns:
            Updated membership instance.
        """
        await self.db.commit()
        return membership

    async def delete(self, tenant_id: str, user_id: str) -> bool:
        """Delete a membership.

        Args:
            tenant_id: Tenant ID.
            user_id: User ID.

        Returns:
            True if deleted, False if not found.
        """
        membership = await self.get(tenant_id, user_id)
        if not membership:
            return False

        await self.db.delete(membership)
        await self.db.commit()
        return True


class WorkspaceMembershipRepository:
    """Repository for WorkspaceMembership model."""

    def __init__(self, db: AsyncSession, ctx: RequestContext):
        """Initialize workspace membership repository.

        Args:
            db: Database session.
            ctx: Request context.
        """
        self.db = db
        self.ctx = ctx

    async def get(self, workspace_id: str, user_id: str) -> WorkspaceMembership | None:
        """Get membership.

        Args:
            workspace_id: Workspace ID.
            user_id: User ID.

        Returns:
            WorkspaceMembership instance or None if not found.
        """
        return await self.db.get(
            WorkspaceMembership,
            (self.ctx.tenant_id, workspace_id, user_id)
        )

    async def get_by_workspace(self, workspace_id: str) -> list[WorkspaceMembership]:
        """Get all memberships for a workspace.

        Args:
            workspace_id: Workspace ID.

        Returns:
            List of WorkspaceMembership instances.
        """
        query = select(WorkspaceMembership).where(
            and_(
                WorkspaceMembership.tenant_id == self.ctx.tenant_id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        results = list((await self.db.exec(query)).scalars().all())
        return _unwrap_all(results)

    async def get_by_user(self, user_id: str) -> list[WorkspaceMembership]:
        """Get all workspace memberships for a user.

        Args:
            user_id: User ID.

        Returns:
            List of WorkspaceMembership instances.
        """
        query = select(WorkspaceMembership).where(
            and_(
                WorkspaceMembership.tenant_id == self.ctx.tenant_id,
                WorkspaceMembership.user_id == user_id,
            )
        )
        results = list((await self.db.exec(query)).scalars().all())
        return _unwrap_all(results)

    async def create(self, membership: WorkspaceMembership) -> WorkspaceMembership:
        """Create a new membership.

        Args:
            membership: Membership instance to create.

        Returns:
            Created membership instance.
        """
        # Ensure tenant_id matches context
        membership.tenant_id = self.ctx.tenant_id
        self.db.add(membership)
        await self.db.commit()
        return membership

    async def update(self, membership: WorkspaceMembership) -> WorkspaceMembership:
        """Update an existing membership.

        Args:
            membership: Membership instance to update.

        Returns:
            Updated membership instance.
        """
        await self.db.commit()
        return membership

    async def delete(self, workspace_id: str, user_id: str) -> bool:
        """Delete a membership.

        Args:
            workspace_id: Workspace ID.
            user_id: User ID.

        Returns:
            True if deleted, False if not found.
        """
        membership = await self.get(workspace_id, user_id)
        if not membership:
            return False

        await self.db.delete(membership)
        await self.db.commit()
        return True


class UserSessionRepository:
    """Repository for sign-in sessions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, session: UserSession) -> UserSession:
        self.db.add(session)
        await self.db.commit()
        return session

    async def get_by_id(self, session_id: str) -> UserSession | None:
        return await self.db.get(UserSession, session_id)

    async def get_by_refresh_hash(self, refresh_hash: str) -> UserSession | None:
        query = select(UserSession).where(UserSession.refresh_token_hash == refresh_hash)
        return _unwrap_result((await self.db.exec(query)).scalars().first())

    async def list_by_user(self, user_id: str, *, include_ended: bool = False) -> list[UserSession]:
        clauses = [UserSession.user_id == user_id]
        if not include_ended:
            clauses.append(UserSession.status == "active")
        query = (
            select(UserSession)
            .where(and_(*clauses))
            .order_by(UserSession.last_seen_at.desc())
        )
        return _unwrap_all(list((await self.db.exec(query)).scalars().all()))

    async def save(self, session: UserSession) -> UserSession:
        self.db.add(session)
        await self.db.commit()
        return session

    async def last_seen_for_users(self, user_ids: list[str]) -> dict[str, datetime]:
        """Return the most recent activity per user across their sessions."""
        if not user_ids:
            return {}
        query = (
            select(UserSession.user_id, func.max(UserSession.last_seen_at))
            .where(UserSession.user_id.in_(user_ids))
            .group_by(UserSession.user_id)
        )
        seen: dict[str, datetime] = {}
        for row in (await self.db.exec(query)).all():
            user_id, last_seen = row[0], row[1]
            if user_id and last_seen:
                seen[str(user_id)] = last_seen
        return seen


class IdentityTokenRepository:
    """Repository for single-use links the instance mails out."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_hash(self, token_hash: str) -> IdentityToken | None:
        query = select(IdentityToken).where(IdentityToken.token_hash == token_hash)
        return _unwrap_result((await self.db.exec(query)).scalars().first())

    async def supersede_pending(self, user_id: str, purpose: str) -> None:
        """Retire earlier links of the same kind.

        Issuing a second reset link must invalidate the first: otherwise a link
        someone was tricked into requesting stays live alongside the real one.
        """
        query = select(IdentityToken).where(
            and_(
                IdentityToken.user_id == user_id,
                IdentityToken.purpose == purpose,
                IdentityToken.status == "pending",
            )
        )
        for row in _unwrap_all(list((await self.db.exec(query)).scalars().all())):
            row.status = "superseded"
            self.db.add(row)
        await self.db.commit()

    async def save(self, token: IdentityToken) -> IdentityToken:
        self.db.add(token)
        await self.db.commit()
        return token


class WorkspaceInvitationRepository:
    """Repository for offers of workspace membership."""

    def __init__(self, db: AsyncSession, ctx: RequestContext | None = None):
        self.db = db
        self.ctx = ctx

    async def get_by_hash(self, token_hash: str) -> WorkspaceInvitation | None:
        query = select(WorkspaceInvitation).where(
            WorkspaceInvitation.token_hash == token_hash
        )
        return _unwrap_result((await self.db.exec(query)).scalars().first())

    async def get_by_id(self, invitation_id: str) -> WorkspaceInvitation | None:
        return await self.db.get(WorkspaceInvitation, invitation_id)

    async def list_for_workspace(
        self,
        workspace_id: str,
        *,
        include_closed: bool = False,
    ) -> list[WorkspaceInvitation]:
        clauses = [WorkspaceInvitation.workspace_id == workspace_id]
        if not include_closed:
            clauses.append(WorkspaceInvitation.status == "pending")
        query = (
            select(WorkspaceInvitation)
            .where(and_(*clauses))
            .order_by(WorkspaceInvitation.created_at.desc())
        )
        return _unwrap_all(list((await self.db.exec(query)).scalars().all()))

    async def get_pending_for_email(
        self,
        workspace_id: str,
        email: str,
    ) -> WorkspaceInvitation | None:
        query = select(WorkspaceInvitation).where(
            and_(
                WorkspaceInvitation.workspace_id == workspace_id,
                WorkspaceInvitation.email == email,
                WorkspaceInvitation.status == "pending",
            )
        )
        return _unwrap_result((await self.db.exec(query)).scalars().first())

    async def save(self, invitation: WorkspaceInvitation) -> WorkspaceInvitation:
        self.db.add(invitation)
        await self.db.commit()
        return invitation


class AccountDeletionRequestRepository:
    """Repository for account closure requests."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_pending_for_user(self, user_id: str) -> AccountDeletionRequest | None:
        query = select(AccountDeletionRequest).where(
            and_(
                AccountDeletionRequest.user_id == user_id,
                AccountDeletionRequest.status == "pending",
            )
        )
        return _unwrap_result((await self.db.exec(query)).scalars().first())

    async def list_due(self, now: datetime, limit: int = 50) -> list[AccountDeletionRequest]:
        """Requests whose pause has elapsed and which nobody withdrew."""
        query = (
            select(AccountDeletionRequest)
            .where(
                and_(
                    AccountDeletionRequest.status == "pending",
                    AccountDeletionRequest.execute_after <= now,
                )
            )
            .order_by(AccountDeletionRequest.execute_after.asc())
            .limit(limit)
        )
        return _unwrap_all(list((await self.db.exec(query)).scalars().all()))

    async def save(self, request: AccountDeletionRequest) -> AccountDeletionRequest:
        self.db.add(request)
        await self.db.commit()
        return request


class UserMfaRepository:
    """Repository for second-factor enrolments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_user(self, user_id: str) -> UserMfa | None:
        query = select(UserMfa).where(UserMfa.user_id == user_id)
        return _unwrap_result((await self.db.exec(query)).scalars().first())

    async def active_user_ids(self, user_ids: list[str]) -> set[str]:
        """Which of these users have a confirmed second factor."""
        if not user_ids:
            return set()
        query = select(UserMfa.user_id).where(
            and_(UserMfa.user_id.in_(user_ids), UserMfa.status == "active")
        )
        return {str(user_id) for user_id in (await self.db.exec(query)).scalars().all() if user_id}

    async def save(self, enrolment: UserMfa) -> UserMfa:
        self.db.add(enrolment)
        await self.db.commit()
        return enrolment

    async def delete(self, enrolment: UserMfa) -> None:
        await self.db.delete(enrolment)
        await self.db.commit()


class SavedViewRepository:
    """Repository for a user's kept filters, scoped to their workspace."""

    def __init__(self, db: AsyncSession, ctx: RequestContext):
        self.db = db
        self.ctx = ctx

    def _scope(self):
        return [
            SavedView.tenant_id == self.ctx.tenant_id,
            SavedView.workspace_id == self.ctx.workspace_id,
            SavedView.user_id == self.ctx.user_id,
        ]

    async def list(self, surface: str | None = None) -> list[SavedView]:
        clauses = self._scope()
        if surface:
            clauses.append(SavedView.surface == surface)
        query = (
            select(SavedView).where(and_(*clauses)).order_by(SavedView.created_at.asc())
        )
        return _unwrap_all(list((await self.db.exec(query)).scalars().all()))

    async def get(self, view_id: str) -> SavedView | None:
        query = select(SavedView).where(and_(SavedView.id == view_id, *self._scope()))
        return _unwrap_result((await self.db.exec(query)).scalars().first())

    async def get_by_name(self, surface: str, name: str) -> SavedView | None:
        query = select(SavedView).where(
            and_(SavedView.surface == surface, SavedView.name == name, *self._scope())
        )
        return _unwrap_result((await self.db.exec(query)).scalars().first())

    async def save(self, view: SavedView) -> SavedView:
        self.db.add(view)
        await self.db.commit()
        return view

    async def clear_default(self, surface: str, *, except_id: str | None = None) -> None:
        """Only one view per surface may be the default."""
        for row in await self.list(surface):
            if row.is_default and row.id != except_id:
                row.is_default = False
                self.db.add(row)
        await self.db.commit()

    async def delete(self, view: SavedView) -> None:
        await self.db.delete(view)
        await self.db.commit()


class PinnedObjectRepository:
    """Repository for a user's pinned objects, scoped to their workspace."""

    def __init__(self, db: AsyncSession, ctx: RequestContext):
        self.db = db
        self.ctx = ctx

    def _scope(self):
        return [
            PinnedObject.tenant_id == self.ctx.tenant_id,
            PinnedObject.workspace_id == self.ctx.workspace_id,
            PinnedObject.user_id == self.ctx.user_id,
        ]

    async def list(self) -> list[PinnedObject]:
        query = (
            select(PinnedObject)
            .where(and_(*self._scope()))
            .order_by(PinnedObject.created_at.desc())
        )
        return _unwrap_all(list((await self.db.exec(query)).scalars().all()))

    async def get(self, pin_id: str) -> PinnedObject | None:
        query = select(PinnedObject).where(and_(PinnedObject.id == pin_id, *self._scope()))
        return _unwrap_result((await self.db.exec(query)).scalars().first())

    async def get_by_target(self, object_type: str, object_id: str) -> PinnedObject | None:
        query = select(PinnedObject).where(
            and_(
                PinnedObject.object_type == object_type,
                PinnedObject.object_id == object_id,
                *self._scope(),
            )
        )
        return _unwrap_result((await self.db.exec(query)).scalars().first())

    async def save(self, pin: PinnedObject) -> PinnedObject:
        self.db.add(pin)
        await self.db.commit()
        return pin

    async def delete(self, pin: PinnedObject) -> None:
        await self.db.delete(pin)
        await self.db.commit()


class ApiKeyRepository:
    """Repository for API keys."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, key_id: str) -> ApiKey | None:
        return await self.db.get(ApiKey, key_id)

    async def get_by_hash(self, key_hash: str) -> ApiKey | None:
        query = select(ApiKey).where(ApiKey.key_hash == key_hash)
        result = (await self.db.exec(query)).scalars().first()
        return _unwrap_result(result)

    async def list_by_workspace(
        self,
        tenant_id: str,
        workspace_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ApiKey]:
        query = (
            select(ApiKey)
            .where(
                and_(
                    ApiKey.tenant_id == tenant_id,
                    ApiKey.workspace_id == workspace_id,
                )
            )
            .order_by(ApiKey.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        results = list((await self.db.exec(query)).scalars().all())
        return _unwrap_all(results)

    async def list_by_user(self, user_id: str) -> list[ApiKey]:
        """Every key this user issued, across workspaces.

        Closing an account has to reach all of them; scoping by workspace would
        leave keys alive in workspaces the closure never looked at.
        """
        query = select(ApiKey).where(ApiKey.user_id == user_id)
        return _unwrap_all(list((await self.db.exec(query)).scalars().all()))

    async def create(self, api_key: ApiKey) -> ApiKey:
        self.db.add(api_key)
        await self.db.commit()
        return api_key

    async def update(self, api_key: ApiKey) -> ApiKey:
        await self.db.commit()
        return api_key


class ResourceGrantRepository(AsyncRepository[ResourceGrant]):
    """Repository for resource grants."""

    def __init__(self, db: AsyncSession, ctx: RequestContext):
        super().__init__(ResourceGrant, db, ctx)

    async def get_by_resource_user(
        self,
        resource_type: str,
        resource_id: str,
        user_id: str,
    ) -> ResourceGrant | None:
        query = select(ResourceGrant).where(
            and_(
                ResourceGrant.resource_type == resource_type,
                ResourceGrant.resource_id == resource_id,
                ResourceGrant.user_id == user_id,
            )
        )
        query = self._apply_scope(query)
        result = (await self.db.exec(query)).scalars().first()
        return self._unwrap_result(result)

    async def list_by_resource(
        self,
        resource_type: str,
        resource_id: str,
    ) -> list[ResourceGrant]:
        query = select(ResourceGrant).where(
            and_(
                ResourceGrant.resource_type == resource_type,
                ResourceGrant.resource_id == resource_id,
            )
        )
        query = self._apply_scope(query).order_by(ResourceGrant.created_at.desc())
        results = list((await self.db.exec(query)).scalars().all())
        return self._unwrap_all(results)

    async def list_in_scope(
        self,
        *,
        resource_type: str | None = None,
        limit: int = 500,
    ) -> list[ResourceGrant]:
        """List every grant in the current workspace, newest first.

        Used by the access surface, which shows who holds what across the whole
        workspace rather than for one named resource.
        """
        query = select(ResourceGrant)
        if resource_type:
            query = query.where(ResourceGrant.resource_type == resource_type)
        query = self._apply_scope(query).order_by(ResourceGrant.created_at.desc()).limit(limit)
        results = list((await self.db.exec(query)).scalars().all())
        return self._unwrap_all(results)

    async def list_by_user(self, user_id: str) -> list[ResourceGrant]:
        query = select(ResourceGrant).where(ResourceGrant.user_id == user_id)
        query = self._apply_scope(query).order_by(ResourceGrant.created_at.desc())
        results = list((await self.db.exec(query)).scalars().all())
        return self._unwrap_all(results)

    async def delete_by_resource_user(
        self,
        resource_type: str,
        resource_id: str,
        user_id: str,
    ) -> bool:
        grant = await self.get_by_resource_user(resource_type, resource_id, user_id)
        if not grant:
            return False
        await self.db.delete(grant)
        await self.db.commit()
        return True
