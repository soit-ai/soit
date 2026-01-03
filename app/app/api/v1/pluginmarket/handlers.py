""" handlers

PluginMarket request handlers (thin orchestration).
"""

from typing import List, Optional

from app.kernel.contracts.context import RequestContext
from app.kernel.registry.deps import get_registry
from app.modules.pluginmarket.runtime.loader import PluginRuntimeLoader
from app.modules.pluginmarket.application.service import PluginMarketService
from app.modules.pluginmarket.application.schemas import (
    PluginCreate,
    PluginUpdate,
    PluginInstallRequest,
    PluginEnableRequest,
    PluginInstallationResponse,
    PluginPackageInstallResponse,
    PluginResponse,
)
from app.infra.db.pagination import PaginatedResponse, parse_page_params


class PluginMarketHandlers:
    """Handlers for PluginMarket API endpoints."""
    
    def __init__(self, service: PluginMarketService):
        """Initialize plugin market handlers.
        
        Args:
            service: PluginMarketService instance.
        """
        self.service = service
    
    async def create_plugin(
        self,
        ctx: RequestContext,
        plugin_in: PluginCreate,
    ) -> PluginResponse:
        """Create a new plugin.
        
        Args:
            ctx: Request context.
            plugin_in: Plugin creation schema.
            
        Returns:
            Created plugin.
        """
        plugin = self.service.create_plugin(plugin_in)
        return PluginResponse.model_validate(plugin)
    
    async def list_plugins(
        self,
        ctx: RequestContext,
        published_only: bool = False,
        page_token: Optional[str] = None,
        page_size: int = 20,
    ) -> PaginatedResponse[PluginResponse]:
        """List plugins.
        
        Args:
            ctx: Request context.
            published_only: Only return published plugins.
            page_token: Optional page token.
            page_size: Page size.
            
        Returns:
            Paginated plugins.
        """
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        
        plugins = self.service.list_plugins(
            published_only=published_only,
            limit=limit,
            offset=offset,
        )
        
        items = [PluginResponse.model_validate(p) for p in plugins]
        
        has_next = len(plugins) == limit
        next_offset = offset + len(plugins) if has_next else None
        
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )
    
    async def get_plugin(
        self,
        ctx: RequestContext,
        plugin_id: str,
    ) -> PluginResponse:
        """Get plugin by ID.
        
        Args:
            ctx: Request context.
            plugin_id: Plugin ID.
            
        Returns:
            Plugin details.
        """
        plugin = self.service.get_plugin(plugin_id)
        return PluginResponse.model_validate(plugin)
    
    async def update_plugin(
        self,
        ctx: RequestContext,
        plugin_id: str,
        plugin_in: PluginUpdate,
    ) -> PluginResponse:
        """Update plugin.
        
        Args:
            ctx: Request context.
            plugin_id: Plugin ID.
            plugin_in: Plugin update schema.
            
        Returns:
            Updated plugin.
        """
        plugin = self.service.update_plugin(plugin_id, plugin_in)
        return PluginResponse.model_validate(plugin)
    
    async def delete_plugin(
        self,
        ctx: RequestContext,
        plugin_id: str,
    ) -> None:
        """Delete plugin.
        
        Args:
            ctx: Request context.
            plugin_id: Plugin ID.
        """
        self.service.delete_plugin(plugin_id)
    
    async def install_plugin(
        self,
        ctx: RequestContext,
        plugin_id: str,
        install_request: PluginInstallRequest,
    ) -> dict:
        """Install a plugin.
        
        Args:
            ctx: Request context.
            plugin_id: Plugin ID.
            install_request: Installation request.
            
        Returns:
            Installation result.
        """
        installation = self.service.install_plugin(plugin_id, install_request)
        return {
            "id": installation.id,
            "plugin_id": installation.plugin_id,
            "installed_at": installation.created_at.isoformat() if installation.created_at else None,
        }


    async def install_plugin_package(
        self,
        ctx: RequestContext,
        plugin_id: str,
        package_bytes: bytes,
        expected_sha256: Optional[str] = None,
    ) -> PluginPackageInstallResponse:
        """Install plugin package bytes into filesystem."""
        result = self.service.install_plugin_package(plugin_id, package_bytes, expected_sha256=expected_sha256)
        return PluginPackageInstallResponse(**result)

    async def set_plugin_enabled(
        self,
        ctx: RequestContext,
        plugin_id: str,
        req: PluginEnableRequest,
    ) -> PluginInstallationResponse:
        """Enable/disable a plugin installation."""
        inst = self.service.set_plugin_enabled(plugin_id, req.enabled)
        return PluginInstallationResponse(
            id=inst.id,
            plugin_id=inst.plugin_id,
            tenant_id=inst.tenant_id,
            workspace_id=inst.workspace_id,
            config_json=inst.config_json,
            created_at=inst.created_at.isoformat(),
        )




async def reload_runtime(self, ctx: RequestContext) -> dict:
    """Reload installed plugins from filesystem into the in-process registry."""
    loader = PluginRuntimeLoader()
    loaded = loader.load_all()
    return {
        "loaded_count": len(loaded),
        "loaded": [
            {
                "tenant_id": p.tenant_id,
                "workspace_id": p.workspace_id,
                "name": p.name,
                "version": p.version,
                "install_dir": str(p.install_dir),
                "tool_refs": p.tool_refs,
            }
            for p in loaded
        ],
    }

async def list_runtime_tools(self, ctx: RequestContext) -> dict:
    """List tool specs currently registered for this tenant/workspace."""
    reg = get_registry()
    items = reg.list(kind="tool", tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id)
    return {
        "tools": [
            {
                "tool_ref": key.name,
                "version": key.version,
                "plugin": (payload or {}).get("plugin"),
                "tool_spec": (payload or {}).get("tool_spec"),
            }
            for key, payload in items
        ]
    }
