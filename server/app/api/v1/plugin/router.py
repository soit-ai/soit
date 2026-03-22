"""Plugin API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.api.v1.permissions import require_workspace_read_ctx, require_workspace_write_ctx
from app.api.v1.plugin.dependencies import get_plugin_service
from app.api.v1.plugin.handlers import PluginHandlers
from app.infra.db.pagination import PaginatedResponse
from app.kernel.contracts.context import RequestContext
from app.modules.plugin.application.schemas import (
    PluginCreate,
    PluginEnableRequest,
    PluginInstallationResponse,
    PluginInstallRequest,
    PluginPackageInstallResponse,
    PluginResponse,
    PluginRuntimeReloadResponse,
    PluginUpdate,
    PluginUpgradeResponse,
    RuntimeToolListResponse,
)
from app.modules.plugin.application.service import PluginService


router = APIRouter()


@router.post("", response_model=PluginResponse, status_code=status.HTTP_201_CREATED)
async def create_plugin(
    plugin_in: PluginCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: PluginService = Depends(get_plugin_service),
):
    handlers = PluginHandlers(service)
    return await handlers.create_plugin(ctx, plugin_in)


@router.get("", response_model=PaginatedResponse[PluginResponse])
async def list_plugins(
    published_only: bool = False,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: PluginService = Depends(get_plugin_service),
):
    handlers = PluginHandlers(service)
    return await handlers.list_plugins(ctx, published_only, page_token, page_size)


@router.get("/{plugin_id}", response_model=PluginResponse)
async def get_plugin(
    plugin_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: PluginService = Depends(get_plugin_service),
):
    handlers = PluginHandlers(service)
    return await handlers.get_plugin(ctx, plugin_id)


@router.put("/{plugin_id}", response_model=PluginResponse)
async def update_plugin(
    plugin_id: str,
    plugin_in: PluginUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: PluginService = Depends(get_plugin_service),
):
    handlers = PluginHandlers(service)
    return await handlers.update_plugin(ctx, plugin_id, plugin_in)


@router.post("/{plugin_id}/install")
async def install_plugin(
    plugin_id: str,
    install_request: PluginInstallRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: PluginService = Depends(get_plugin_service),
):
    handlers = PluginHandlers(service)
    return await handlers.install_plugin(ctx, plugin_id, install_request)


@router.delete("/{plugin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plugin(
    plugin_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: PluginService = Depends(get_plugin_service),
):
    handlers = PluginHandlers(service)
    await handlers.delete_plugin(ctx, plugin_id)


@router.post("/{plugin_id}/install-package", response_model=PluginPackageInstallResponse)
async def install_plugin_package(
    plugin_id: str,
    package: UploadFile = File(...),
    expected_sha256: Optional[str] = None,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: PluginService = Depends(get_plugin_service),
):
    handlers = PluginHandlers(service)
    package_bytes = await package.read()
    return await handlers.install_plugin_package(ctx, plugin_id, package_bytes, expected_sha256)


@router.post("/{plugin_id}/upgrade-package", response_model=PluginUpgradeResponse)
async def upgrade_plugin_package(
    plugin_id: str,
    package: UploadFile = File(...),
    expected_sha256: Optional[str] = None,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: PluginService = Depends(get_plugin_service),
):
    handlers = PluginHandlers(service)
    package_bytes = await package.read()
    return await handlers.upgrade_plugin_package(ctx, plugin_id, package_bytes, expected_sha256)


@router.delete("/{plugin_id}/install", status_code=status.HTTP_204_NO_CONTENT)
async def uninstall_plugin(
    plugin_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: PluginService = Depends(get_plugin_service),
):
    handlers = PluginHandlers(service)
    await handlers.uninstall_plugin(ctx, plugin_id)


@router.post("/{plugin_id}/enabled", response_model=PluginInstallationResponse)
async def set_plugin_enabled(
    plugin_id: str,
    req: PluginEnableRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: PluginService = Depends(get_plugin_service),
):
    handlers = PluginHandlers(service)
    return await handlers.set_plugin_enabled(ctx, plugin_id, req)


@router.post("/runtime/reload", response_model=PluginRuntimeReloadResponse)
async def reload_plugin_runtime(
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: PluginService = Depends(get_plugin_service),
):
    handlers = PluginHandlers(service)
    return await handlers.reload_runtime(ctx)


@router.get("/runtime/tools", response_model=RuntimeToolListResponse)
async def list_runtime_tools(
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: PluginService = Depends(get_plugin_service),
):
    handlers = PluginHandlers(service)
    return await handlers.list_runtime_tools(ctx)
