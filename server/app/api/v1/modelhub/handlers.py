"""handlers

ModelHub request handlers.
"""

from __future__ import annotations

from typing import Optional

from app.kernel.contracts.context import RequestContext
from app.infra.db.pagination import PaginatedResponse
from app.modules.modelhub.application.service import ModelHubService
from app.modules.modelhub.application.schemas import (
    ProviderCreate,
    ProviderUpdate,
    ProviderResponse,
    PlatformModelResponse,
    ProviderModelCreate,
    ProviderModelUpdate,
    ProviderModelResponse,
    SyncFromPlatformRequest,
    SyncJobResponse,
    HealthcheckResponse,
    ModelTestChatRequest,
    ModelTestEmbeddingRequest,
    ModelTestResponse,
)


class ModelHubHandlers:
    """Handlers for ModelHub API endpoints."""

    def __init__(self, service: ModelHubService):
        self.service = service

    async def list_providers(
        self,
        ctx: RequestContext,
        page_size: int = 200,
    ) -> PaginatedResponse[ProviderResponse]:
        providers = await self.service.list_providers(limit=page_size)
        items = [ProviderResponse.model_validate(item) for item in providers]
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=False,
            next_offset=None,
        )

    async def create_provider(
        self,
        ctx: RequestContext,
        data: ProviderCreate,
    ) -> ProviderResponse:
        provider = await self.service.create_provider(data)
        return ProviderResponse.model_validate(provider)

    async def update_provider(
        self,
        ctx: RequestContext,
        provider_id: str,
        data: ProviderUpdate,
    ) -> ProviderResponse:
        provider = await self.service.update_provider(provider_id, data)
        return ProviderResponse.model_validate(provider)

    async def delete_provider(self, ctx: RequestContext, provider_id: str) -> None:
        await self.service.delete_provider(provider_id)

    async def healthcheck_provider(
        self,
        ctx: RequestContext,
        provider_id: str,
    ) -> HealthcheckResponse:
        result = await self.service.healthcheck_provider(provider_id)
        return HealthcheckResponse.model_validate(result)

    async def list_platform_models(
        self,
        ctx: RequestContext,
        provider_kind: str,
        page_size: int = 200,
    ) -> PaginatedResponse[PlatformModelResponse]:
        models = await self.service.list_platform_models(provider_kind, limit=page_size)
        items = [PlatformModelResponse.model_validate(item) for item in models]
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=False,
            next_offset=None,
        )

    async def refresh_platform_models(
        self,
        ctx: RequestContext,
        provider_id: str,
    ) -> dict:
        return await self.service.refresh_platform_models(provider_id)

    async def list_provider_models(
        self,
        ctx: RequestContext,
        provider_id: str,
        page_size: int = 200,
    ) -> PaginatedResponse[ProviderModelResponse]:
        models = await self.service.list_provider_models(provider_id, limit=page_size)
        items = [ProviderModelResponse.model_validate(item) for item in models]
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=False,
            next_offset=None,
        )

    async def create_provider_model(
        self,
        ctx: RequestContext,
        provider_id: str,
        data: ProviderModelCreate,
    ) -> ProviderModelResponse:
        model = await self.service.create_provider_model(provider_id, data)
        return ProviderModelResponse.model_validate(model)

    async def update_provider_model(
        self,
        ctx: RequestContext,
        provider_id: str,
        provider_model_id: str,
        data: ProviderModelUpdate,
    ) -> ProviderModelResponse:
        model = await self.service.update_provider_model(provider_id, provider_model_id, data)
        return ProviderModelResponse.model_validate(model)

    async def delete_provider_model(
        self,
        ctx: RequestContext,
        provider_id: str,
        provider_model_id: str,
    ) -> None:
        await self.service.delete_provider_model(provider_id, provider_model_id)

    async def sync_from_platform(
        self,
        ctx: RequestContext,
        provider_id: str,
        data: Optional[SyncFromPlatformRequest],
    ) -> SyncJobResponse:
        job = await self.service.sync_from_platform(provider_id, data)
        return SyncJobResponse.model_validate(job)

    async def list_sync_jobs(
        self,
        ctx: RequestContext,
        provider_id: str,
        page_size: int = 50,
    ) -> PaginatedResponse[SyncJobResponse]:
        jobs = await self.service.list_sync_jobs(provider_id, limit=page_size)
        items = [SyncJobResponse.model_validate(item) for item in jobs]
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=False,
            next_offset=None,
        )

    async def test_chat(
        self,
        ctx: RequestContext,
        data: ModelTestChatRequest,
    ) -> ModelTestResponse:
        result = await self.service.test_chat(data)
        return ModelTestResponse.model_validate(result)

    async def test_embeddings(
        self,
        ctx: RequestContext,
        data: ModelTestEmbeddingRequest,
    ) -> ModelTestResponse:
        result = await self.service.test_embeddings(data)
        return ModelTestResponse.model_validate(result)
