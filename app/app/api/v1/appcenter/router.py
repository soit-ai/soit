""" router

AppCenter API routes (FastAPI).
"""

from typing import Optional
from fastapi import APIRouter, Depends, status

from app.kernel.contracts.context import RequestContext
from app.api.v1.permissions import require_workspace_read_ctx, require_workspace_write_ctx
from app.infra.db.pagination import PaginatedResponse
from app.modules.appcenter.application.schemas import (
    AppCreate,
    AppUpdate,
    AppVersionCreate,
    AppPublish,
    AppSetCurrentVersion,
    AppCloneRequest,
    AppImportRequest,
    AppResponse,
    AppVersionResponse,
    AppMarketResponse,
    AppInstallRequest,
    AppInstallationResponse,
    AppComponentResponse,
    AppComponentEdgeResponse,
    AppVersionRefResponse,
    RefImpactResponse,
    AppExportResponse,
    AppVersionCompareRequest,
    AppVersionCompareResponse,
)
from app.modules.appcenter.application.service import AppService
from app.api.v1.appcenter.dependencies import get_appcenter_service
from app.api.v1.appcenter.handlers import AppCenterHandlers


router = APIRouter()


@router.post("", response_model=AppResponse, status_code=status.HTTP_201_CREATED)
async def create_app(
    app_in: AppCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    """Create a new app."""
    handlers = AppCenterHandlers(service)
    return await handlers.create_app(ctx, app_in)


@router.get("", response_model=PaginatedResponse[AppResponse])
async def list_apps(
    search: Optional[str] = None,
    app_type: Optional[str] = None,
    status: Optional[str] = None,
    visibility: Optional[str] = None,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    """List apps."""
    handlers = AppCenterHandlers(service)
    return await handlers.list_apps(
        ctx,
        page_token=page_token,
        page_size=page_size,
        search=search,
        app_type=app_type,
        status=status,
        visibility=visibility,
    )


@router.get("/{app_id}", response_model=AppResponse)
async def get_app(
    app_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    """Get app detail."""
    handlers = AppCenterHandlers(service)
    return await handlers.get_app(ctx, app_id)


@router.put("/{app_id}", response_model=AppResponse)
async def update_app(
    app_id: str,
    app_in: AppUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    """Update app."""
    handlers = AppCenterHandlers(service)
    return await handlers.update_app(ctx, app_id, app_in)


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_app(
    app_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    """Delete app."""
    handlers = AppCenterHandlers(service)
    await handlers.delete_app(ctx, app_id)


@router.post("/{app_id}/versions", response_model=AppVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_version(
    app_id: str,
    version_in: AppVersionCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    """Create app version."""
    handlers = AppCenterHandlers(service)
    return await handlers.create_version(ctx, app_id, version_in)


@router.post("/{app_id}/versions/{version_id}/set-current", response_model=AppResponse)
async def set_current_version(
    app_id: str,
    version_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    handlers = AppCenterHandlers(service)
    return await handlers.set_current_version(ctx, app_id, version_id)


@router.get("/{app_id}/versions", response_model=list[AppVersionResponse])
async def list_versions(
    app_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    """List app versions."""
    handlers = AppCenterHandlers(service)
    return await handlers.list_versions(ctx, app_id)


@router.get("/{app_id}/versions/{version_id}/components", response_model=list[AppComponentResponse])
async def list_components(
    app_id: str,
    version_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    """List components for app version."""
    handlers = AppCenterHandlers(service)
    return await handlers.list_components(ctx, app_id, version_id)


@router.get("/{app_id}/versions/{version_id}/edges", response_model=list[AppComponentEdgeResponse])
async def list_edges(
    app_id: str,
    version_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    """List edges for app version."""
    handlers = AppCenterHandlers(service)
    return await handlers.list_edges(ctx, app_id, version_id)


@router.get("/{app_id}/versions/{version_id}/refs", response_model=list[AppVersionRefResponse])
async def list_refs(
    app_id: str,
    version_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    """List refs for app version."""
    handlers = AppCenterHandlers(service)
    return await handlers.list_refs(ctx, app_id, version_id)


@router.get("/{app_id}/versions/{version_id}/export", response_model=AppExportResponse)
async def export_version(
    app_id: str,
    version_id: str,
    format: str = "json",
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    handlers = AppCenterHandlers(service)
    return await handlers.export_version(ctx, app_id, version_id, format=format)


@router.post("/{app_id}/versions/compare", response_model=AppVersionCompareResponse)
async def compare_versions(
    app_id: str,
    data: AppVersionCompareRequest,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    handlers = AppCenterHandlers(service)
    return await handlers.compare_versions(ctx, app_id, data)


@router.get("/refs/impact", response_model=RefImpactResponse)
async def impact_refs(
    ref_type: str,
    ref_id: Optional[str] = None,
    ref_key: Optional[str] = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    """Impact analysis for references."""
    handlers = AppCenterHandlers(service)
    return await handlers.impact_refs(ctx, ref_type, ref_id=ref_id, ref_key=ref_key)


@router.post("/{app_id}/publish", response_model=AppMarketResponse)
async def publish_app(
    app_id: str,
    publish_in: AppPublish,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    """Publish app to marketplace."""
    handlers = AppCenterHandlers(service)
    return await handlers.publish_app(ctx, app_id, publish_in)


@router.post("/{app_id}/clone", response_model=AppResponse, status_code=status.HTTP_201_CREATED)
async def clone_app(
    app_id: str,
    data: AppCloneRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    handlers = AppCenterHandlers(service)
    return await handlers.clone_app(ctx, app_id, data)


@router.post("/import", response_model=AppResponse, status_code=status.HTTP_201_CREATED)
async def import_app(
    data: AppImportRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    handlers = AppCenterHandlers(service)
    return await handlers.import_app(ctx, data)


@router.post("/{app_id}/install", response_model=AppInstallationResponse)
async def install_app(
    app_id: str,
    install_in: AppInstallRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    """Install app into workspace."""
    handlers = AppCenterHandlers(service)
    return await handlers.install_app(ctx, app_id, install_in)


@router.get("/installations", response_model=list[AppInstallationResponse])
async def list_installations(
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    """List app installations."""
    handlers = AppCenterHandlers(service)
    return await handlers.list_installations(ctx)


@router.delete("/installations/{installation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def uninstall_app(
    installation_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    """Uninstall app from workspace."""
    handlers = AppCenterHandlers(service)
    await handlers.uninstall_app(ctx, installation_id)


@router.get("/marketplace", response_model=PaginatedResponse[AppMarketResponse])
async def list_marketplace(
    category: Optional[str] = None,
    featured: Optional[bool] = None,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: AppService = Depends(get_appcenter_service),
):
    """List marketplace apps."""
    handlers = AppCenterHandlers(service)
    return await handlers.list_marketplace(
        ctx,
        page_token=page_token,
        page_size=page_size,
        category=category,
        featured=featured,
    )
