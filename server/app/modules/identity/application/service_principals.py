""" service_principals

Service principals: non-human callers of a workspace with a human owner.

Setting one up is a governance act, since its keys act on the workspace
without a person signing in: only workspace owners and admins may create,
change or remove one. A principal never acts above its owner, both here, when
its role is set, and at every call, where the owner's current role caps it.
"""

from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.rbac import WORKSPACE_ROLE_RANK
from app.modules.identity.application.ports import (
    ServicePrincipalRepositoryPort,
    WorkspaceMembershipRepositoryPort,
)
from app.modules.identity.application.schemas import (
    ServicePrincipalCreate,
    ServicePrincipalUpdate,
)
from app.modules.identity.domain.models import ServicePrincipal


class ServicePrincipalService:
    """Create and change a workspace's service principals."""

    def __init__(
        self,
        db: AsyncSession,
        ctx: RequestContext,
        repo: ServicePrincipalRepositoryPort,
        memberships: WorkspaceMembershipRepositoryPort,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.repo = repo
        self.memberships = memberships

    def _require_governor(self) -> None:
        if not self.ctx.can_govern():
            raise ForbiddenError("Workspace owner or admin role required to manage service principals")

    async def _check_owner(self, owner_user_id: str, role: str) -> None:
        membership = await self.memberships.get(self.ctx.workspace_id, owner_user_id)
        if membership is None:
            raise ValidationError(
                "The owner must be a member of this workspace",
                {"param": "owner_user_id"},
            )
        if WORKSPACE_ROLE_RANK.get(role, 0) > WORKSPACE_ROLE_RANK.get(membership.role, 0):
            raise ValidationError(
                "A service principal cannot hold a higher role than its owner",
                {"param": "workspace_role"},
            )

    async def _get(self, principal_id: str) -> ServicePrincipal:
        principal = await self.repo.get_by_id(principal_id)
        if principal is None:
            raise NotFoundError(f"Service principal not found: {principal_id}")
        return principal

    async def list_principals(self) -> list[ServicePrincipal]:
        if not self.ctx.can_read():
            raise ForbiddenError("Workspace read permission required")
        return list(await self.repo.list_all())

    async def get_principal(self, principal_id: str) -> ServicePrincipal:
        if not self.ctx.can_read():
            raise ForbiddenError("Workspace read permission required")
        return await self._get(principal_id)

    async def create_principal(self, data: ServicePrincipalCreate) -> ServicePrincipal:
        self._require_governor()
        if await self.repo.get_by_name(data.name) is not None:
            raise ConflictError(f"A service principal named {data.name} already exists")
        owner = data.owner_user_id or self.ctx.user_id
        await self._check_owner(owner, data.workspace_role)
        return await self.repo.create(
            ServicePrincipal(
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                name=data.name,
                description=data.description,
                owner_user_id=owner,
                workspace_role=data.workspace_role,
                created_by=self.ctx.user_id,
            )
        )

    async def update_principal(
        self,
        principal_id: str,
        data: ServicePrincipalUpdate,
    ) -> ServicePrincipal:
        self._require_governor()
        principal = await self._get(principal_id)
        changes = data.model_dump(exclude_unset=True)
        if changes.get("name") is not None and changes["name"] != principal.name:
            if await self.repo.get_by_name(changes["name"]) is not None:
                raise ConflictError(f"A service principal named {changes['name']} already exists")
            principal.name = changes["name"]
        if "description" in changes:
            principal.description = changes["description"]
        owner = changes.get("owner_user_id") or principal.owner_user_id
        role = changes.get("workspace_role") or principal.workspace_role
        if owner != principal.owner_user_id or role != principal.workspace_role:
            await self._check_owner(owner, role)
            principal.owner_user_id = owner
            principal.workspace_role = role
        if changes.get("status") is not None:
            principal.status = changes["status"]
        principal.updated_at = utc_now()
        return await self.repo.update(principal)

    async def delete_principal(self, principal_id: str) -> None:
        self._require_governor()
        if not await self.repo.delete(principal_id):
            raise NotFoundError(f"Service principal not found: {principal_id}")
