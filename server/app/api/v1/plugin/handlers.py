"""Plugin request handlers."""

from typing import Optional

from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.contracts.context import RequestContext
from app.kernel.registry.deps import get_registry
from app.modules.plugin.application.schemas import (
    PluginArtifactResponse,
    PluginCapabilityResponse,
    PluginCreate,
    PluginEnableRequest,
    PluginInstallationResponse,
    PluginPackageInstallResponse,
    PluginPackageUploadResponse,
    PluginPublishRequest,
    PluginReleaseResponse,
    PluginResponse,
    PluginRollbackRequest,
    PluginUpdate,
    PluginUpgradeResponse,
    PluginVersionCreate,
    PluginVersionResponse,
)
from app.modules.plugin.application.service import PluginService
from app.modules.plugin.runtime.loader import PluginRuntimeLoader


class PluginHandlers:
    """Handlers for plugin API endpoints."""

    def __init__(self, service: PluginService):
        self.service = service

    def _as_plugin_response(self, plugin, installation=None) -> PluginResponse:
        base = PluginResponse.model_validate(
            {
                "id": plugin.id,
                "name": plugin.name,
                "version": plugin.version,
                "publisher": plugin.publisher,
                "plugin_type": plugin.plugin_type,
                "status": plugin.status,
                "description": plugin.description,
                "spec_json": plugin.spec_json,
                "manifest_json": plugin.manifest_json,
                "metadata_json": plugin.metadata_json,
                "publish_status": self.service.publish_status_for(plugin),
                "installed_count": plugin.installed_count,
                "current_version_id": plugin.current_version_id,
                "published_version_id": plugin.published_version_id,
                "installed": installation is not None,
                "enabled": None,
                "installation_id": None,
                "installed_at": None,
                "created_by": plugin.created_by,
                "created_at": plugin.created_at,
                "updated_at": plugin.updated_at,
            }
        )
        if not installation:
            return base
        cfg = installation.config_json or {}
        return base.model_copy(
            update={
                "enabled": bool(cfg.get("enabled", True)),
                "installation_id": installation.id,
                "installed_at": installation.created_at,
            }
        )

    async def create_plugin(self, ctx: RequestContext, plugin_in: PluginCreate) -> PluginResponse:
        plugin = await self.service.create_plugin(plugin_in)
        return self._as_plugin_response(plugin)

    async def list_plugins(
        self,
        ctx: RequestContext,
        published_only: bool = False,
        plugin_type: Optional[str] = None,
        page_token: Optional[str] = None,
        page_size: int = 20,
    ) -> PaginatedResponse[PluginResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        plugins = await self.service.list_plugins(
            published_only=published_only,
            plugin_type=plugin_type,
            limit=limit,
            offset=offset,
        )

        items: list[PluginResponse] = []
        for plugin in plugins:
            installation = self.service.get_installation_for_plugin(plugin.id)
            items.append(self._as_plugin_response(plugin, installation))

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
        return self._as_plugin_response(plugin, installation)

    async def update_plugin(self, ctx: RequestContext, plugin_id: str, plugin_in: PluginUpdate) -> PluginResponse:
        plugin = await self.service.update_plugin(plugin_id, plugin_in)
        installation = self.service.get_installation_for_plugin(plugin.id)
        return self._as_plugin_response(plugin, installation)

    async def create_version(
        self,
        ctx: RequestContext,
        plugin_id: str,
        payload: PluginVersionCreate,
    ) -> PluginVersionResponse:
        return PluginVersionResponse.model_validate(await self.service.create_version(plugin_id, payload))

    async def list_versions(
        self,
        ctx: RequestContext,
        plugin_id: str,
        *,
        page_token: Optional[str] = None,
        page_size: int = 20,
    ) -> PaginatedResponse[PluginVersionResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        rows = await self.service.list_versions(plugin_id, limit=limit, offset=offset)
        items = [PluginVersionResponse.model_validate(item) for item in rows]
        has_next = len(rows) == limit
        next_offset = offset + len(rows) if has_next else None
        return PaginatedResponse.create(items=items, page_size=len(items), has_next=has_next, next_offset=next_offset)

    async def list_releases(
        self,
        ctx: RequestContext,
        plugin_id: str,
        *,
        page_token: Optional[str] = None,
        page_size: int = 20,
    ) -> PaginatedResponse[PluginReleaseResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        rows = await self.service.list_releases(plugin_id, limit=limit, offset=offset)
        items = [
            PluginReleaseResponse.model_validate(
                {
                    "id": row.id,
                    "plugin_id": row.plugin_id,
                    "version_id": row.plugin_version_id,
                    "action": row.action,
                    "scope": row.scope,
                    "status": row.status,
                    "from_version_id": row.from_version_id,
                    "to_version_id": row.to_version_id,
                    "notes": row.notes,
                    "rollback_of_publish_id": row.rollback_of_publish_id,
                    "created_by": row.created_by,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at,
                }
            )
            for row in rows
        ]
        has_next = len(rows) == limit
        next_offset = offset + len(rows) if has_next else None
        return PaginatedResponse.create(items=items, page_size=len(items), has_next=has_next, next_offset=next_offset)

    async def publish_version(
        self,
        ctx: RequestContext,
        plugin_id: str,
        payload: PluginPublishRequest,
    ) -> PluginResponse:
        plugin = await self.service.publish_version(plugin_id, payload.version_id, notes=payload.notes)
        return self._as_plugin_response(plugin, self.service.get_installation_for_plugin(plugin.id))

    async def rollback_version(
        self,
        ctx: RequestContext,
        plugin_id: str,
        payload: PluginRollbackRequest,
    ) -> PluginResponse:
        plugin = await self.service.rollback_version(plugin_id, payload.version_id, notes=payload.notes)
        return self._as_plugin_response(plugin, self.service.get_installation_for_plugin(plugin.id))

    async def list_installations(
        self,
        ctx: RequestContext,
        plugin_id: str,
        *,
        page_token: Optional[str] = None,
        page_size: int = 20,
    ) -> PaginatedResponse[PluginInstallationResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        rows = self.service.list_installations_for_plugin(plugin_id)[offset : offset + limit]
        items = [PluginInstallationResponse.model_validate(item) for item in rows]
        has_next = len(rows) == limit
        next_offset = offset + len(rows) if has_next else None
        return PaginatedResponse.create(items=items, page_size=len(items), has_next=has_next, next_offset=next_offset)

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

    async def upload_plugin_package(
        self,
        ctx: RequestContext,
        package_bytes: bytes,
        *,
        mode: str = "auto",
        expected_sha256: Optional[str] = None,
    ) -> PluginPackageUploadResponse:
        result = await self.service.upload_plugin_package(
            package_bytes,
            mode=mode,
            expected_sha256=expected_sha256,
        )
        plugin = result["plugin"]
        return PluginPackageUploadResponse(
            action=result["action"],
            plugin=self._as_plugin_response(plugin, self.service.get_installation_for_plugin(plugin.id)),
            install=PluginPackageInstallResponse(**result["install"]),
        )

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
            plugin=self._as_plugin_response(plugin, self.service.get_installation_for_plugin(plugin.id)),
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
            plugin_version_id=inst.plugin_version_id,
            tenant_id=inst.tenant_id,
            workspace_id=inst.workspace_id,
            enabled=inst.enabled,
            state=inst.state,
            config_json=inst.config_json,
            created_at=inst.created_at,
            updated_at=inst.updated_at,
        )

    async def list_artifacts(
        self,
        ctx: RequestContext,
        *,
        plugin_id: Optional[str],
        artifact_kind: Optional[str],
        enabled: Optional[bool],
        page_token: Optional[str] = None,
        page_size: int = 20,
    ) -> PaginatedResponse[PluginArtifactResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        rows = await self.service.list_artifacts(
            plugin_id=plugin_id,
            artifact_kind=artifact_kind,
            enabled=enabled,
            limit=limit,
            offset=offset,
        )
        items = [PluginArtifactResponse.model_validate(item) for item in rows]
        has_next = len(rows) == limit
        next_offset = offset + len(rows) if has_next else None
        return PaginatedResponse.create(items=items, page_size=len(items), has_next=has_next, next_offset=next_offset)

    async def list_capabilities(
        self,
        ctx: RequestContext,
        *,
        kind: Optional[str],
        page_token: Optional[str] = None,
        page_size: int = 100,
    ) -> PaginatedResponse[PluginCapabilityResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        rows = await self.service.list_capabilities(kind=kind, limit=limit, offset=offset)
        items = [PluginCapabilityResponse.model_validate(item) for item in rows]
        has_next = len(rows) == limit
        next_offset = offset + len(rows) if has_next else None
        return PaginatedResponse.create(items=items, page_size=len(items), has_next=has_next, next_offset=next_offset)

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
