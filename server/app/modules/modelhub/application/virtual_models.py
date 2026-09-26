""" virtual_models

Workspace virtual models: one name a call uses, served by the first of an
ordered list of models that can answer. The LLM policy gateway does the
failing over; this service keeps the lists.
"""

from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import ConflictError, NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.guard import workspace_guard
from app.modules.modelhub.application.ports import (
    ModelRefCatalogPort,
    VirtualModelRepositoryPort,
)
from app.modules.modelhub.application.schemas import (
    VirtualModelCreate,
    VirtualModelUpdate,
)
from app.modules.modelhub.domain.models import VirtualModel


class VirtualModelService:
    """Create and change a workspace's virtual models."""

    def __init__(
        self,
        db: AsyncSession,
        ctx: RequestContext,
        repo: VirtualModelRepositoryPort,
        catalog: ModelRefCatalogPort,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.repo = repo
        self.catalog = catalog

    async def _require_known_targets(self, targets: list[str]) -> None:
        # A misspelt target would only surface as a skipped attempt when the
        # earlier targets fail, which is the worst moment to find it.
        unknown = await self.catalog.unknown_refs(targets)
        if unknown:
            raise ValidationError(
                "Targets must be models of this workspace",
                {"param": "targets", "unknown": unknown},
            )

    async def _get(self, virtual_model_id: str) -> VirtualModel:
        model = await self.repo.get_by_id(virtual_model_id)
        if model is None:
            raise NotFoundError(f"Virtual model not found: {virtual_model_id}")
        return model

    @workspace_guard("read")
    async def list_virtual_models(self, limit: int = 200) -> list[VirtualModel]:
        return list(await self.repo.list_all(limit=limit))

    @workspace_guard("read")
    async def get_virtual_model(self, virtual_model_id: str) -> VirtualModel:
        return await self._get(virtual_model_id)

    @workspace_guard("write")
    async def create_virtual_model(self, data: VirtualModelCreate) -> VirtualModel:
        if await self.repo.get_by_slug(data.slug) is not None:
            raise ConflictError(f"A virtual model named {data.slug} already exists")
        await self._require_known_targets(data.targets)
        return await self.repo.create(
            VirtualModel(
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                slug=data.slug,
                name=data.name,
                description=data.description,
                targets_json=data.targets,
                created_by=self.ctx.user_id,
            )
        )

    @workspace_guard("write")
    async def update_virtual_model(
        self,
        virtual_model_id: str,
        data: VirtualModelUpdate,
    ) -> VirtualModel:
        model = await self._get(virtual_model_id)
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes:
            if changes["name"] is None:
                raise ValidationError("A virtual model needs a name")
            model.name = changes["name"]
        if "description" in changes:
            model.description = changes["description"]
        if "targets" in changes:
            if changes["targets"] is None:
                raise ValidationError("A virtual model needs at least one target")
            await self._require_known_targets(changes["targets"])
            model.targets_json = changes["targets"]
        if "status" in changes and changes["status"] is not None:
            model.status = changes["status"]
        model.updated_at = utc_now()
        return await self.repo.update(model)

    @workspace_guard("write")
    async def delete_virtual_model(self, virtual_model_id: str) -> None:
        if not await self.repo.delete(virtual_model_id):
            raise NotFoundError(f"Virtual model not found: {virtual_model_id}")
