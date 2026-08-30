""" repository

Identity repositories using scope-aware base.
"""


from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.infra.db.repository import Repository
from app.kernel.contracts.context import RequestContext
from app.modules.identity.domain.models import (
    ApiKey,
    PinnedObject,
    ResourceGrant,
    SavedView,
    Tenant,
    TenantMembership,
    User,
    UserMfa,
    UserSession,
    Workspace,
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

    def __init__(self, db: Session):
        """Initialize user repository.

        Args:
            db: Database session.
        """
        self.db = db

    def get_by_id(self, user_id: str) -> User | None:
        """Get user by ID.

        Args:
            user_id: User ID.

        Returns:
            User instance or None if not found.
        """
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        """Get user by email.

        Args:
            email: User email.

        Returns:
            User instance or None if not found.
        """
        query = select(User).where(User.email == email)
        result = self.db.exec(query).first()
        return _unwrap_result(result)

    def create(self, user: User) -> User:
        """Create a new user.

        Args:
            user: User instance to create.

        Returns:
            Created user instance.
        """
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user: User) -> User:
        """Update an existing user.

        Args:
            user: User instance to update.

        Returns:
            Updated user instance.
        """
        self.db.commit()
        self.db.refresh(user)
        return user


class TenantRepository:
    """Repository for Tenant model (global scope)."""

    def __init__(self, db: Session):
        """Initialize tenant repository.

        Args:
            db: Database session.
        """
        self.db = db

    def get_by_id(self, tenant_id: str) -> Tenant | None:
        """Get tenant by ID.

        Args:
            tenant_id: Tenant ID.

        Returns:
            Tenant instance or None if not found.
        """
        return self.db.get(Tenant, tenant_id)

    def get_by_name(self, name: str) -> Tenant | None:
        """Get tenant by name.

        Args:
            name: Tenant name.

        Returns:
            Tenant instance or None if not found.
        """
        query = select(Tenant).where(Tenant.name == name)
        result = self.db.exec(query).first()
        return _unwrap_result(result)

    def create(self, tenant: Tenant) -> Tenant:
        """Create a new tenant.

        Args:
            tenant: Tenant instance to create.

        Returns:
            Created tenant instance.
        """
        self.db.add(tenant)
        self.db.commit()
        self.db.refresh(tenant)
        return tenant

    def update(self, tenant: Tenant) -> Tenant:
        """Update an existing tenant.

        Args:
            tenant: Tenant instance to update.

        Returns:
            Updated tenant instance.
        """
        self.db.commit()
        self.db.refresh(tenant)
        return tenant


class WorkspaceRepository(Repository[Workspace]):
    """Repository for Workspace model."""

    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize workspace repository.

        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(Workspace, db, ctx)

    def get_by_name(self, name: str) -> Workspace | None:
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
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def list_by_tenant(self) -> list[Workspace]:
        """List all workspaces in tenant.

        Returns:
            List of Workspace instances.
        """
        query = select(Workspace).where(
            Workspace.tenant_id == self.ctx.tenant_id
        ).order_by(Workspace.created_at.desc())
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)


class TenantMembershipRepository:
    """Repository for TenantMembership model."""

    def __init__(self, db: Session):
        """Initialize tenant membership repository.

        Args:
            db: Database session.
        """
        self.db = db

    def get(self, tenant_id: str, user_id: str) -> TenantMembership | None:
        """Get membership.

        Args:
            tenant_id: Tenant ID.
            user_id: User ID.

        Returns:
            TenantMembership instance or None if not found.
        """
        return self.db.get(TenantMembership, (tenant_id, user_id))

    def get_by_user(self, user_id: str) -> list[TenantMembership]:
        """Get all memberships for a user.

        Args:
            user_id: User ID.

        Returns:
            List of TenantMembership instances.
        """
        query = select(TenantMembership).where(
            TenantMembership.user_id == user_id
        )
        results = list(self.db.exec(query).all())
        return _unwrap_all(results)

    def get_by_tenant(self, tenant_id: str) -> list[TenantMembership]:
        """Get all memberships for a tenant.

        Args:
            tenant_id: Tenant ID.

        Returns:
            List of TenantMembership instances.
        """
        query = select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id
        )
        results = list(self.db.exec(query).all())
        return _unwrap_all(results)

    def create(self, membership: TenantMembership) -> TenantMembership:
        """Create a new membership.

        Args:
            membership: Membership instance to create.

        Returns:
            Created membership instance.
        """
        self.db.add(membership)
        self.db.commit()
        self.db.refresh(membership)
        return membership

    def update(self, membership: TenantMembership) -> TenantMembership:
        """Update an existing membership.

        Args:
            membership: Membership instance to update.

        Returns:
            Updated membership instance.
        """
        self.db.commit()
        self.db.refresh(membership)
        return membership

    def delete(self, tenant_id: str, user_id: str) -> bool:
        """Delete a membership.

        Args:
            tenant_id: Tenant ID.
            user_id: User ID.

        Returns:
            True if deleted, False if not found.
        """
        membership = self.get(tenant_id, user_id)
        if not membership:
            return False

        self.db.delete(membership)
        self.db.commit()
        return True


class WorkspaceMembershipRepository:
    """Repository for WorkspaceMembership model."""

    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize workspace membership repository.

        Args:
            db: Database session.
            ctx: Request context.
        """
        self.db = db
        self.ctx = ctx

    def get(self, workspace_id: str, user_id: str) -> WorkspaceMembership | None:
        """Get membership.

        Args:
            workspace_id: Workspace ID.
            user_id: User ID.

        Returns:
            WorkspaceMembership instance or None if not found.
        """
        return self.db.get(
            WorkspaceMembership,
            (self.ctx.tenant_id, workspace_id, user_id)
        )

    def get_by_workspace(self, workspace_id: str) -> list[WorkspaceMembership]:
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
        results = list(self.db.exec(query).all())
        return _unwrap_all(results)

    def get_by_user(self, user_id: str) -> list[WorkspaceMembership]:
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
        results = list(self.db.exec(query).all())
        return _unwrap_all(results)

    def create(self, membership: WorkspaceMembership) -> WorkspaceMembership:
        """Create a new membership.

        Args:
            membership: Membership instance to create.

        Returns:
            Created membership instance.
        """
        # Ensure tenant_id matches context
        membership.tenant_id = self.ctx.tenant_id
        self.db.add(membership)
        self.db.commit()
        self.db.refresh(membership)
        return membership

    def update(self, membership: WorkspaceMembership) -> WorkspaceMembership:
        """Update an existing membership.

        Args:
            membership: Membership instance to update.

        Returns:
            Updated membership instance.
        """
        self.db.commit()
        self.db.refresh(membership)
        return membership

    def delete(self, workspace_id: str, user_id: str) -> bool:
        """Delete a membership.

        Args:
            workspace_id: Workspace ID.
            user_id: User ID.

        Returns:
            True if deleted, False if not found.
        """
        membership = self.get(workspace_id, user_id)
        if not membership:
            return False

        self.db.delete(membership)
        self.db.commit()
        return True


class UserSessionRepository:
    """Repository for sign-in sessions."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, session: UserSession) -> UserSession:
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_by_id(self, session_id: str) -> UserSession | None:
        return self.db.get(UserSession, session_id)

    def get_by_refresh_hash(self, refresh_hash: str) -> UserSession | None:
        query = select(UserSession).where(UserSession.refresh_token_hash == refresh_hash)
        return _unwrap_result(self.db.exec(query).first())

    def list_by_user(self, user_id: str, *, include_ended: bool = False) -> list[UserSession]:
        clauses = [UserSession.user_id == user_id]
        if not include_ended:
            clauses.append(UserSession.status == "active")
        query = (
            select(UserSession)
            .where(and_(*clauses))
            .order_by(UserSession.last_seen_at.desc())
        )
        return _unwrap_all(list(self.db.exec(query).all()))

    def save(self, session: UserSession) -> UserSession:
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def last_seen_for_users(self, user_ids: list[str]) -> dict[str, datetime]:
        """Return the most recent activity per user across their sessions."""
        if not user_ids:
            return {}
        query = (
            select(UserSession.user_id, func.max(UserSession.last_seen_at))
            .where(UserSession.user_id.in_(user_ids))
            .group_by(UserSession.user_id)
        )
        seen: dict[str, datetime] = {}
        for row in self.db.exec(query).all():
            user_id, last_seen = row[0], row[1]
            if user_id and last_seen:
                seen[str(user_id)] = last_seen
        return seen


class UserMfaRepository:
    """Repository for second-factor enrolments."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_user(self, user_id: str) -> UserMfa | None:
        query = select(UserMfa).where(UserMfa.user_id == user_id)
        return _unwrap_result(self.db.exec(query).first())

    def active_user_ids(self, user_ids: list[str]) -> set[str]:
        """Which of these users have a confirmed second factor."""
        if not user_ids:
            return set()
        query = select(UserMfa.user_id).where(
            and_(UserMfa.user_id.in_(user_ids), UserMfa.status == "active")
        )
        return {str(row[0]) for row in self.db.exec(query).all() if row[0]}

    def save(self, enrolment: UserMfa) -> UserMfa:
        self.db.add(enrolment)
        self.db.commit()
        self.db.refresh(enrolment)
        return enrolment

    def delete(self, enrolment: UserMfa) -> None:
        self.db.delete(enrolment)
        self.db.commit()


class SavedViewRepository:
    """Repository for a user's kept filters, scoped to their workspace."""

    def __init__(self, db: Session, ctx: RequestContext):
        self.db = db
        self.ctx = ctx

    def _scope(self):
        return [
            SavedView.tenant_id == self.ctx.tenant_id,
            SavedView.workspace_id == self.ctx.workspace_id,
            SavedView.user_id == self.ctx.user_id,
        ]

    def list(self, surface: str | None = None) -> list[SavedView]:
        clauses = self._scope()
        if surface:
            clauses.append(SavedView.surface == surface)
        query = (
            select(SavedView).where(and_(*clauses)).order_by(SavedView.created_at.asc())
        )
        return _unwrap_all(list(self.db.exec(query).all()))

    def get(self, view_id: str) -> SavedView | None:
        query = select(SavedView).where(and_(SavedView.id == view_id, *self._scope()))
        return _unwrap_result(self.db.exec(query).first())

    def get_by_name(self, surface: str, name: str) -> SavedView | None:
        query = select(SavedView).where(
            and_(SavedView.surface == surface, SavedView.name == name, *self._scope())
        )
        return _unwrap_result(self.db.exec(query).first())

    def save(self, view: SavedView) -> SavedView:
        self.db.add(view)
        self.db.commit()
        self.db.refresh(view)
        return view

    def clear_default(self, surface: str, *, except_id: str | None = None) -> None:
        """Only one view per surface may be the default."""
        for row in self.list(surface):
            if row.is_default and row.id != except_id:
                row.is_default = False
                self.db.add(row)
        self.db.commit()

    def delete(self, view: SavedView) -> None:
        self.db.delete(view)
        self.db.commit()


class PinnedObjectRepository:
    """Repository for a user's pinned objects, scoped to their workspace."""

    def __init__(self, db: Session, ctx: RequestContext):
        self.db = db
        self.ctx = ctx

    def _scope(self):
        return [
            PinnedObject.tenant_id == self.ctx.tenant_id,
            PinnedObject.workspace_id == self.ctx.workspace_id,
            PinnedObject.user_id == self.ctx.user_id,
        ]

    def list(self) -> list[PinnedObject]:
        query = (
            select(PinnedObject)
            .where(and_(*self._scope()))
            .order_by(PinnedObject.created_at.desc())
        )
        return _unwrap_all(list(self.db.exec(query).all()))

    def get(self, pin_id: str) -> PinnedObject | None:
        query = select(PinnedObject).where(and_(PinnedObject.id == pin_id, *self._scope()))
        return _unwrap_result(self.db.exec(query).first())

    def get_by_target(self, object_type: str, object_id: str) -> PinnedObject | None:
        query = select(PinnedObject).where(
            and_(
                PinnedObject.object_type == object_type,
                PinnedObject.object_id == object_id,
                *self._scope(),
            )
        )
        return _unwrap_result(self.db.exec(query).first())

    def save(self, pin: PinnedObject) -> PinnedObject:
        self.db.add(pin)
        self.db.commit()
        self.db.refresh(pin)
        return pin

    def delete(self, pin: PinnedObject) -> None:
        self.db.delete(pin)
        self.db.commit()


class ApiKeyRepository:
    """Repository for API keys."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, key_id: str) -> ApiKey | None:
        return self.db.get(ApiKey, key_id)

    def get_by_hash(self, key_hash: str) -> ApiKey | None:
        query = select(ApiKey).where(ApiKey.key_hash == key_hash)
        result = self.db.exec(query).first()
        return _unwrap_result(result)

    def list_by_workspace(
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
        results = list(self.db.exec(query).all())
        return _unwrap_all(results)

    def create(self, api_key: ApiKey) -> ApiKey:
        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)
        return api_key

    def update(self, api_key: ApiKey) -> ApiKey:
        self.db.commit()
        self.db.refresh(api_key)
        return api_key


class ResourceGrantRepository(Repository[ResourceGrant]):
    """Repository for resource grants."""

    def __init__(self, db: Session, ctx: RequestContext):
        super().__init__(ResourceGrant, db, ctx)

    def get_by_resource_user(
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
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def list_by_resource(
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
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)

    def list_in_scope(
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
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)

    def list_by_user(self, user_id: str) -> list[ResourceGrant]:
        query = select(ResourceGrant).where(ResourceGrant.user_id == user_id)
        query = self._apply_scope(query).order_by(ResourceGrant.created_at.desc())
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)

    def delete_by_resource_user(
        self,
        resource_type: str,
        resource_id: str,
        user_id: str,
    ) -> bool:
        grant = self.get_by_resource_user(resource_type, resource_id, user_id)
        if not grant:
            return False
        self.db.delete(grant)
        self.db.commit()
        return True
