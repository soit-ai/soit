"""Model refs checked against the workspace's providers and models."""

from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.contracts.context import RequestContext
from app.modules.modelhub.infra.repository import (
    ProviderModelRepository,
    ProviderRepository,
)


class WorkspaceModelRefCatalog:
    """Which ``model:{provider}:{model_id}`` refs name a model of the workspace."""

    def __init__(self, db: AsyncSession, ctx: RequestContext) -> None:
        self.providers = ProviderRepository(db, ctx)
        self.models = ProviderModelRepository(db, ctx)

    async def unknown_refs(self, model_refs: list[str]) -> list[str]:
        unknown: list[str] = []
        for ref in model_refs:
            _, slug, model_id = ref.split(":", 2)
            provider = await self.providers.get_by_slug(slug)
            if provider is None:
                unknown.append(ref)
                continue
            model = await self.models.get_by_provider_and_model_id(provider.id, model_id)
            if model is None:
                unknown.append(ref)
        return unknown
