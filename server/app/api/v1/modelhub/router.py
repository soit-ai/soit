"""router

ModelHub API routes.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, status

from app.kernel.contracts.context import RequestContext
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.api.v1.modelhub.dependencies import get_modelhub_service
from app.api.v1.modelhub.handlers import ModelHubHandlers
from app.infra.db.pagination import PaginatedResponse
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
from app.modules.modelhub.application.service import ModelHubService


router = APIRouter()


@router.get("/providers", response_model=PaginatedResponse[ProviderResponse])
async def list_providers(
    page_size: int = 200,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ModelHubService = Depends(get_modelhub_service),
):
    handlers = ModelHubHandlers(service)
    return await handlers.list_providers(ctx, page_size=page_size)


@router.post("/providers", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    data: ProviderCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ModelHubService = Depends(get_modelhub_service),
):
    handlers = ModelHubHandlers(service)
    return await handlers.create_provider(ctx, data)


@router.patch("/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: str,
    data: ProviderUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ModelHubService = Depends(get_modelhub_service),
):
    handlers = ModelHubHandlers(service)
    return await handlers.update_provider(ctx, provider_id, data)


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ModelHubService = Depends(get_modelhub_service),
):
    handlers = ModelHubHandlers(service)
    await handlers.delete_provider(ctx, provider_id)


@router.post("/providers/{provider_id}/healthcheck", response_model=HealthcheckResponse)
async def healthcheck_provider(
    provider_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ModelHubService = Depends(get_modelhub_service),
):
    handlers = ModelHubHandlers(service)
    return await handlers.healthcheck_provider(ctx, provider_id)


@router.post("/providers/{provider_id}/sync-from-platform", response_model=SyncJobResponse)
async def sync_from_platform(
    provider_id: str,
    data: Optional[SyncFromPlatformRequest] = None,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ModelHubService = Depends(get_modelhub_service),
):
    handlers = ModelHubHandlers(service)
    return await handlers.sync_from_platform(ctx, provider_id, data)


@router.get("/providers/{provider_id}/sync-jobs", response_model=PaginatedResponse[SyncJobResponse])
async def list_sync_jobs(
    provider_id: str,
    page_size: int = 50,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ModelHubService = Depends(get_modelhub_service),
):
    handlers = ModelHubHandlers(service)
    return await handlers.list_sync_jobs(ctx, provider_id, page_size=page_size)


@router.get("/providers/{provider_id}/models", response_model=PaginatedResponse[ProviderModelResponse])
async def list_provider_models(
    provider_id: str,
    page_size: int = 200,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ModelHubService = Depends(get_modelhub_service),
):
    handlers = ModelHubHandlers(service)
    return await handlers.list_provider_models(ctx, provider_id, page_size=page_size)


@router.post("/providers/{provider_id}/models", response_model=ProviderModelResponse, status_code=status.HTTP_201_CREATED)
async def create_provider_model(
    provider_id: str,
    data: ProviderModelCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ModelHubService = Depends(get_modelhub_service),
):
    handlers = ModelHubHandlers(service)
    return await handlers.create_provider_model(ctx, provider_id, data)


@router.patch("/providers/{provider_id}/models/{provider_model_id}", response_model=ProviderModelResponse)
async def update_provider_model(
    provider_id: str,
    provider_model_id: str,
    data: ProviderModelUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ModelHubService = Depends(get_modelhub_service),
):
    handlers = ModelHubHandlers(service)
    return await handlers.update_provider_model(ctx, provider_id, provider_model_id, data)


@router.delete("/providers/{provider_id}/models/{provider_model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_model(
    provider_id: str,
    provider_model_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ModelHubService = Depends(get_modelhub_service),
):
    handlers = ModelHubHandlers(service)
    await handlers.delete_provider_model(ctx, provider_id, provider_model_id)


@router.get("/platform-models", response_model=PaginatedResponse[PlatformModelResponse])
async def list_platform_models(
    provider_kind: str,
    page_size: int = 200,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: ModelHubService = Depends(get_modelhub_service),
):
    handlers = ModelHubHandlers(service)
    return await handlers.list_platform_models(ctx, provider_kind, page_size=page_size)


@router.post("/platform-models/sync")
async def refresh_platform_models(
    provider_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ModelHubService = Depends(get_modelhub_service),
):
    handlers = ModelHubHandlers(service)
    return await handlers.refresh_platform_models(ctx, provider_id)


@router.post("/test/chat", response_model=ModelTestResponse)
async def test_chat(
    data: ModelTestChatRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ModelHubService = Depends(get_modelhub_service),
):
    handlers = ModelHubHandlers(service)
    return await handlers.test_chat(ctx, data)


@router.post("/test/embeddings", response_model=ModelTestResponse)
async def test_embeddings(
    data: ModelTestEmbeddingRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: ModelHubService = Depends(get_modelhub_service),
):
    handlers = ModelHubHandlers(service)
    return await handlers.test_embeddings(ctx, data)
