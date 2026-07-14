"""handlers

ModelHub request handlers.
"""

from __future__ import annotations

from typing import Optional

from app.kernel.contracts.context import RequestContext
from app.infra.db.pagination import PaginatedResponse
from app.infra.db.pagination import parse_page_params
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
    ProviderSupportMatrixResponse,
    ProviderSupportStatusResponse,
    ModelWorkbenchOverviewResponse,
    ModelWorkbenchModelsResponse,
    ModelWorkbenchProvidersResponse,
    ModelTestChatRequest,
    ModelTestEmbeddingRequest,
    ModelTestResponse,
)


class ModelHubHandlers:
    """Handlers for ModelHub API endpoints."""

    def __init__(self, service: ModelHubService):
        self.service = service

    def _as_platform_model_response(self, model) -> PlatformModelResponse:
        return PlatformModelResponse.model_validate(
            {
                "id": model.id,
                "provider_kind": model.provider_kind,
                "model_id": model.model_id,
                "display_name": model.display_name,
                "capabilities_json": model.capabilities_json,
                "context_window": model.context_window,
                "max_output_tokens": model.max_output_tokens,
                "status": model.status,
                "lifecycle_status": model.lifecycle_status,
                "raw_meta": model.raw_meta,
                "last_seen_at": model.last_seen_at,
                "created_at": model.created_at,
                "updated_at": model.updated_at,
            }
        )

    def _as_provider_model_response(self, model) -> ProviderModelResponse:
        return ProviderModelResponse.model_validate(
            {
                "id": model.id,
                "provider_id": model.provider_id,
                "provider_kind": model.provider_kind,
                "model_id": model.model_id,
                "display_name": model.display_name,
                "description": model.description,
                "capabilities_json": model.capabilities_json,
                "config_json": model.config_json,
                "context_window": model.context_window,
                "max_output_tokens": model.max_output_tokens,
                "status": model.status,
                "lifecycle_status": model.lifecycle_status,
                "raw_meta": model.raw_meta,
                "source": model.source,
                "platform_model_id": model.platform_model_id,
                "sync_status": model.sync_status,
                "user_overrides_json": model.user_overrides_json,
                "last_synced_at": model.last_synced_at,
                "created_at": model.created_at,
                "updated_at": model.updated_at,
            }
        )

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

    async def get_provider_support_matrix(
        self,
        ctx: RequestContext,
    ) -> ProviderSupportMatrixResponse:
        items = await self.service.get_provider_support_matrix()
        return ProviderSupportMatrixResponse(
            providers=[ProviderSupportStatusResponse.model_validate(item) for item in items]
        )

    async def get_workbench_overview(
        self,
        ctx: RequestContext,
    ) -> ModelWorkbenchOverviewResponse:
        return await self.service.get_workbench_overview()

    async def get_workbench_models(
        self,
        ctx: RequestContext,
        page_token: Optional[str],
        page_size: int,
        tab: Optional[str],
        keyword: Optional[str],
        provider_id: Optional[str],
        status: Optional[str],
        model_type: Optional[str],
    ) -> ModelWorkbenchModelsResponse:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        return await self.service.get_workbench_models(
            limit=limit,
            offset=offset,
            tab=tab,
            keyword=keyword,
            provider_id=provider_id,
            status=status,
            model_type=model_type,
        )

    async def get_workbench_providers(
        self,
        ctx: RequestContext,
        page_token: Optional[str],
        page_size: int,
        tab: Optional[str],
        keyword: Optional[str],
        status: Optional[str],
        model_type: Optional[str],
    ) -> ModelWorkbenchProvidersResponse:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        return await self.service.get_workbench_providers(
            limit=limit,
            offset=offset,
            tab=tab,
            keyword=keyword,
            status=status,
            model_type=model_type,
        )

    async def list_platform_models(
        self,
        ctx: RequestContext,
        provider_kind: str,
        page_size: int = 200,
    ) -> PaginatedResponse[PlatformModelResponse]:
        models = await self.service.list_platform_models(provider_kind, limit=page_size)
        items = [self._as_platform_model_response(item) for item in models]
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
        status: Optional[str] = None,
    ) -> PaginatedResponse[ProviderModelResponse]:
        models = await self.service.list_provider_models(provider_id, limit=page_size, status=status)
        items = [self._as_provider_model_response(item) for item in models]
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
        return self._as_provider_model_response(model)

    async def update_provider_model(
        self,
        ctx: RequestContext,
        provider_id: str,
        provider_model_id: str,
        data: ProviderModelUpdate,
    ) -> ProviderModelResponse:
        model = await self.service.update_provider_model(provider_id, provider_model_id, data)
        return self._as_provider_model_response(model)

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
