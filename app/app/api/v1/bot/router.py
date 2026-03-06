""" router

Bot API routes (FastAPI).
"""

from datetime import datetime
from typing import Optional, Dict, Any, Literal
from fastapi import APIRouter, Depends, Body, status

from app.kernel.contracts.context import RequestContext
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.modules.bot.application.app_facade import BotAppFacadeService
from app.modules.bot.application.schemas import (
    BotCreate,
    BotUpdate,
    BotResponse,
    BotVersionCreate,
    BotVersionUpdate,
    BotVersionResponse,
    BotPublishRequest,
    BotExecuteRequest,
    BotTriggerExecuteRequest,
    BotExecuteResponse,
    BotMetricsResponse,
    BotRunLogEntry,
)
from app.infra.db.pagination import PaginatedResponse
from app.api.v1.bot.dependencies import get_bot_service
from app.api.v1.bot.handlers import BotHandlers


router = APIRouter()


@router.post("", response_model=BotResponse, status_code=status.HTTP_201_CREATED)
async def create_bot(
    bot_in: BotCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: BotAppFacadeService = Depends(get_bot_service),
):
    handlers = BotHandlers(service)
    return await handlers.create_bot(ctx, bot_in)


@router.get("", response_model=PaginatedResponse[BotResponse])
async def list_bots(
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: BotAppFacadeService = Depends(get_bot_service),
):
    handlers = BotHandlers(service)
    return await handlers.list_bots(ctx, page_token=page_token, page_size=page_size)


@router.get("/{bot_id}", response_model=BotResponse)
async def get_bot(
    bot_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: BotAppFacadeService = Depends(get_bot_service),
):
    handlers = BotHandlers(service)
    return await handlers.get_bot(ctx, bot_id)


@router.put("/{bot_id}", response_model=BotResponse)
async def update_bot(
    bot_id: str,
    bot_in: BotUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: BotAppFacadeService = Depends(get_bot_service),
):
    handlers = BotHandlers(service)
    return await handlers.update_bot(ctx, bot_id, bot_in)


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bot(
    bot_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: BotAppFacadeService = Depends(get_bot_service),
):
    handlers = BotHandlers(service)
    await handlers.delete_bot(ctx, bot_id)


@router.post("/{bot_id}/versions", response_model=BotVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_version(
    bot_id: str,
    version_in: BotVersionCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: BotAppFacadeService = Depends(get_bot_service),
):
    handlers = BotHandlers(service)
    return await handlers.create_version(ctx, bot_id, version_in)


@router.get("/{bot_id}/versions/{version_id}", response_model=BotVersionResponse)
async def get_version(
    bot_id: str,
    version_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: BotAppFacadeService = Depends(get_bot_service),
):
    handlers = BotHandlers(service)
    return await handlers.get_version(ctx, bot_id, version_id)


@router.put("/{bot_id}/versions/{version_id}", response_model=BotVersionResponse)
async def update_version(
    bot_id: str,
    version_id: str,
    version_in: BotVersionUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: BotAppFacadeService = Depends(get_bot_service),
):
    handlers = BotHandlers(service)
    return await handlers.update_version(ctx, bot_id, version_id, version_in)


@router.get("/{bot_id}/versions", response_model=PaginatedResponse[BotVersionResponse])
async def list_versions(
    bot_id: str,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: BotAppFacadeService = Depends(get_bot_service),
):
    handlers = BotHandlers(service)
    return await handlers.list_versions(ctx, bot_id, page_token=page_token, page_size=page_size)


@router.post("/{bot_id}/publish", response_model=BotResponse)
async def publish_version(
    bot_id: str,
    data: BotPublishRequest = Body(...),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: BotAppFacadeService = Depends(get_bot_service),
):
    handlers = BotHandlers(service)
    return await handlers.publish_version(ctx, bot_id, data)


@router.post("/{bot_id}/execute", response_model=BotExecuteResponse)
async def execute_bot(
    bot_id: str,
    data: BotExecuteRequest = Body(...),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: BotAppFacadeService = Depends(get_bot_service),
):
    handlers = BotHandlers(service)
    return await handlers.execute_bot(ctx, bot_id, data)


@router.post("/{bot_id}/execute/{trigger}", response_model=BotExecuteResponse)
async def execute_bot_trigger(
    bot_id: str,
    trigger: Literal["webhook", "schedule", "event"],
    data: BotTriggerExecuteRequest = Body(default=BotTriggerExecuteRequest()),
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: BotAppFacadeService = Depends(get_bot_service),
):
    handlers = BotHandlers(service)
    return await handlers.execute_bot_trigger(ctx, bot_id, trigger, data)


@router.get("/{bot_id}/runs", response_model=PaginatedResponse[Dict[str, Any]])
async def list_runs(
    bot_id: str,
    page_token: Optional[str] = None,
    page_size: int = 20,
    status: Optional[str] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: BotAppFacadeService = Depends(get_bot_service),
):
    handlers = BotHandlers(service)
    return await handlers.list_runs(
        ctx,
        bot_id,
        page_token=page_token,
        page_size=page_size,
        status=status,
        started_after=started_after,
        started_before=started_before,
    )


@router.get("/{bot_id}/runs/{run_id}")
async def get_run(
    bot_id: str,
    run_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: BotAppFacadeService = Depends(get_bot_service),
):
    handlers = BotHandlers(service)
    return await handlers.get_run(ctx, bot_id, run_id)


@router.get("/{bot_id}/logs", response_model=PaginatedResponse[BotRunLogEntry])
async def list_logs(
    bot_id: str,
    page_token: Optional[str] = None,
    page_size: int = 50,
    status: Optional[str] = None,
    level: Optional[str] = None,
    started_after: Optional[datetime] = None,
    started_before: Optional[datetime] = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: BotAppFacadeService = Depends(get_bot_service),
):
    handlers = BotHandlers(service)
    return await handlers.list_logs(
        ctx,
        bot_id,
        page_token=page_token,
        page_size=page_size,
        status=status,
        level=level,
        started_after=started_after,
        started_before=started_before,
    )


@router.get("/{bot_id}/metrics", response_model=BotMetricsResponse)
async def get_metrics(
    bot_id: str,
    range_key: str = "7d",
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: BotAppFacadeService = Depends(get_bot_service),
):
    handlers = BotHandlers(service)
    return await handlers.get_metrics(ctx, bot_id, range_key=range_key)
