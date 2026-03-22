"""Plugin request handlers."""

from typing import Optional

from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.contracts.context import RequestContext
from app.kernel.registry.deps import get_registry
from app.modules.plugin.application.schemas import (
    PluginCreate,
    PluginEnableRequest,
    PluginInstallationResponse,
    PluginPackageInstallResponse,
    PluginResponse,
    PluginUpdate,
    PluginUpgradeResponse,
)
from app.modules.plugin.application.service import PluginService
from app.modules.plugin.runtime.loader import PluginRuntimeLoader


class PluginHandlers:
    """Handlers for plugin API endpoints."""

    def __init__(self, service: PluginService):
        self.service = service

    async def create_plugin(self, ctx: RequestContext, plugin_in: PluginCreate) -> PluginResponse:
        plugin = await self.service.create_plugin(plugin_in)
        return PluginResponse.model_validate(plugin)

    async def list_plugins(
        self,
        ctx: RequestContext,
        published_only: bool = False,
        page_token: Optional[str] = None,
        page_size: int = 20,
    ) -> PaginatedResponse[PluginResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        plugins = await self.service.list_plugins(published_only=published_only, limit=limit, offset=offset)

        items: list[PluginResponse] = []
        for plugin in plugins:
            installation = self.service.get_installation_for_plugin(plugin.id)
            base = PluginResponse.model_validate(plugin)
            enabled = None
            installation_id = None
            installed_at = None
            if installation:
                cfg = installation.config_json or {}
                enabled = bool(cfg.get("enabled", True))
                installation_id = installation.id
                installed_at = installation.created_at
            items.append(
                base.model_copy(
                    update={
                        "installed": installation is not None,
                        "enabled": enabled,
                        "installation_id": installation_id,
                        "installed_at": installed_at,
                    }
                )
            )

        has_next = len(plugins) == limit
        next_offset = offset + len(plugins) if has_next else None
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )

    async def get_plugin(self, ctx: RequestContext, plugin_id: str) -> PluginResponse:
        plugin = await self.service.get_plugin(plugin_id)
        installation = self.service.get_installation_for_plugin(plugin.id)
        base = PluginResponse.model_validate(plugin)
        enabled = None
        installation_id = None
        installed_at = None
        if installation:
            cfg = installation.config_json or {}
            enabled = bool(cfg.get("enabled", True))
            installation_id = installation.id
            installed_at = installation.created_at
        return base.model_copy(
            update={
                "installed": installation is not None,
                "enabled": enabled,
                "installation_id": installation_id,
                "installed_at": installed_at,
            }
        )

    async def update_plugin(self, ctx: RequestContext, plugin_id: str, plugin_in: PluginUpdate) -> PluginResponse:
        plugin = await self.service.update_plugin(plugin_id, plugin_in)
        return PluginResponse.model_validate(plugin)

    async def delete_plugin(self, ctx: RequestContext, plugin_id: str) -> None:
        await self.service.delete_plugin(plugin_id)

    async def install_plugin(self, ctx: RequestContext, plugin_id: str, install_request):
        installation = await self.service.install_plugin(plugin_id, install_request)
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
        result = await self.service.install_plugin_package(plugin_id, package_bytes, expected_sha256=expected_sha256)
        return PluginPackageInstallResponse(**result)

    async def uninstall_plugin(self, ctx: RequestContext, plugin_id: str) -> None:
        await self.service.uninstall_plugin(plugin_id)

    async def upgrade_plugin_package(
        self,
        ctx: RequestContext,
        plugin_id: str,
        package_bytes: bytes,
        expected_sha256: Optional[str] = None,
    ) -> PluginUpgradeResponse:
        result = await self.service.upgrade_plugin_package(plugin_id, package_bytes, expected_sha256=expected_sha256)
        plugin = await self.service.get_plugin(plugin_id)
        return PluginUpgradeResponse(
            plugin=PluginResponse.model_validate(plugin),
            install=PluginPackageInstallResponse(**result),
        )

    async def set_plugin_enabled(
        self,
        ctx: RequestContext,
        plugin_id: str,
        req: PluginEnableRequest,
    ) -> PluginInstallationResponse:
        inst = await self.service.set_plugin_enabled(plugin_id, req.enabled)
        return PluginInstallationResponse(
            id=inst.id,
            plugin_id=inst.plugin_id,
            tenant_id=inst.tenant_id,
            workspace_id=inst.workspace_id,
            config_json=inst.config_json,
            created_at=inst.created_at,
        )

    async def reload_runtime(self, ctx: RequestContext) -> dict:
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
                    "node_refs": p.node_refs,
                }
                for p in loaded
            ],
        }

    async def list_runtime_tools(self, ctx: RequestContext) -> dict:
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
