""" router

PluginMarket API routes (FastAPI).
"""

from typing import Optional
from fastapi import APIRouter, Depends, status

from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.domains.pluginmarket.service import PluginMarketService
from app.modules.domains.pluginmarket.schemas import (
    PluginCreate,
    PluginUpdate,
    PluginInstallRequest,
    PluginResponse,
)
from app.modules.entrypoints.pluginmarket.dependencies import get_pluginmarket_service
from app.modules.entrypoints.pluginmarket.handlers import PluginMarketHandlers
from app.kernel.db.pagination import PaginatedResponse


router = APIRouter()


@router.post("", response_model=PluginResponse, status_code=status.HTTP_201_CREATED)
async def create_plugin(
    plugin_in: PluginCreate,
    ctx: RequestContext = Depends(get_current_context),
    service: PluginMarketService = Depends(get_pluginmarket_service),
):
    """Create a new plugin.
    
    Args:
        plugin_in: Plugin creation data.
        ctx: Request context.
        service: PluginMarketService instance.
        
    Returns:
        Created plugin.
    """
    handlers = PluginMarketHandlers(service)
    return await handlers.create_plugin(ctx, plugin_in)


@router.get("", response_model=PaginatedResponse[PluginResponse])
async def list_plugins(
    published_only: bool = False,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(get_current_context),
    service: PluginMarketService = Depends(get_pluginmarket_service),
):
    """List plugins.
    
    Args:
        published_only: Only return published plugins.
        page_token: Optional page token.
        page_size: Page size.
        ctx: Request context.
        service: PluginMarketService instance.
        
    Returns:
        Paginated plugins.
    """
    handlers = PluginMarketHandlers(service)
    return await handlers.list_plugins(ctx, published_only, page_token, page_size)


@router.get("/{plugin_id}", response_model=PluginResponse)
async def get_plugin(
    plugin_id: str,
    ctx: RequestContext = Depends(get_current_context),
    service: PluginMarketService = Depends(get_pluginmarket_service),
):
    """Get plugin by ID.
    
    Args:
        plugin_id: Plugin ID.
        ctx: Request context.
        service: PluginMarketService instance.
        
    Returns:
        Plugin details.
    """
    handlers = PluginMarketHandlers(service)
    return await handlers.get_plugin(ctx, plugin_id)


@router.put("/{plugin_id}", response_model=PluginResponse)
async def update_plugin(
    plugin_id: str,
    plugin_in: PluginUpdate,
    ctx: RequestContext = Depends(get_current_context),
    service: PluginMarketService = Depends(get_pluginmarket_service),
):
    """Update plugin.
    
    Args:
        plugin_id: Plugin ID.
        plugin_in: Plugin update data.
        ctx: Request context.
        service: PluginMarketService instance.
        
    Returns:
        Updated plugin.
    """
    handlers = PluginMarketHandlers(service)
    return await handlers.update_plugin(ctx, plugin_id, plugin_in)


@router.post("/{plugin_id}/install")
async def install_plugin(
    plugin_id: str,
    install_request: PluginInstallRequest,
    ctx: RequestContext = Depends(get_current_context),
    service: PluginMarketService = Depends(get_pluginmarket_service),
):
    """Install a plugin.
    
    Args:
        plugin_id: Plugin ID.
        install_request: Installation request.
        ctx: Request context.
        service: PluginMarketService instance.
        
    Returns:
        Installation result.
    """
    handlers = PluginMarketHandlers(service)
    return await handlers.install_plugin(ctx, plugin_id, install_request)


@router.delete("/{plugin_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plugin(
    plugin_id: str,
    ctx: RequestContext = Depends(get_current_context),
    service: PluginMarketService = Depends(get_pluginmarket_service),
):
    """Delete plugin.
    
    Args:
        plugin_id: Plugin ID.
        ctx: Request context.
        service: PluginMarketService instance.
    """
    handlers = PluginMarketHandlers(service)
    await handlers.delete_plugin(ctx, plugin_id)



