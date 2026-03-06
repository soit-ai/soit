""" service

PluginMarket domain service.
"""

import json
import shutil
import hashlib
from typing import Optional, List, Dict, Any, Tuple, Set
from pathlib import Path
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
import logging

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now
from app.settings.settings import settings
from app.kernel.registry.deps import get_registry
from app.modules.pluginmarket.runtime.loader import PluginRuntimeLoader
from app.modules.pluginmarket.domain.models import Plugin, PluginInstallation
from app.modules.pluginmarket.application.ports import PluginRepositoryPort, PluginInstallationRepositoryPort, PluginInstallerPort
from app.modules.pluginmarket.application.schemas import PluginCreate, PluginUpdate, PluginInstallRequest
from app.kernel.identity.guard import rbac_guard, workspace_guard
from app.kernel.identity.permissions import RESOURCE_PLUGIN
from app.modules.appcenter.domain.models import App, AppVersion, AppMarket

logger = logging.getLogger(__name__)

class PluginMarketService:
    """PluginMarket domain service."""
    
    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        plugin_repo: PluginRepositoryPort,
        installation_repo: PluginInstallationRepositoryPort,
        installer: PluginInstallerPort,
    ):
        """Initialize plugin market service.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        self.db = db
        self.ctx = ctx
        self.plugin_repo = plugin_repo
        self.installation_repo = installation_repo
        self.installer = installer
        self.settings = settings


    def _resolve_plugin_create_id(self, plugin_in: PluginCreate, **kwargs) -> str:
        """Resolve plugin id for create RBAC checks."""
        return plugin_in.name or f"new:{self.ctx.workspace_id}"

    def get_installation_for_plugin(self, plugin_id: str) -> Optional[PluginInstallation]:
        """Return installation info for a plugin in this workspace."""
        return self.installation_repo.get_by_plugin(plugin_id)


    def _install_dir_for(self, *, plugin_name: str, version: str) -> Path:
        """Return install directory path for a plugin version in current scope."""
        root = Path(self.settings.plugins_dir).resolve()
        return root / "installed" / self.ctx.tenant_id / self.ctx.workspace_id / plugin_name / version

    def _packages_dir_for(self, *, plugin_name: str, version: str) -> Path:
        root = Path(self.settings.plugins_dir).resolve()
        return root / "packages" / self.ctx.tenant_id / self.ctx.workspace_id / plugin_name / version

    def _prune_empty_dirs(self, path: Path) -> None:
        current = path
        root = Path(self.settings.plugins_dir).resolve()
        while current != root and current.exists():
            if any(current.iterdir()):
                break
            current.rmdir()
            current = current.parent

    def _remove_plugin_files(self, *, plugin_name: str, version: str) -> None:
        install_dir = self._install_dir_for(plugin_name=plugin_name, version=version)
        packages_dir = self._packages_dir_for(plugin_name=plugin_name, version=version)
        if install_dir.exists():
            shutil.rmtree(install_dir, ignore_errors=True)
            self._prune_empty_dirs(install_dir.parent)
        if packages_dir.exists():
            shutil.rmtree(packages_dir, ignore_errors=True)
            self._prune_empty_dirs(packages_dir.parent)

    def _parse_version(self, value: Optional[str]) -> Optional[Tuple[int, int, int]]:
        if not value:
            return None
        parts = value.split(".")
        numbers: list[int] = []
        for part in parts:
            digits = ""
            for ch in part:
                if ch.isdigit():
                    digits += ch
                else:
                    break
            if digits == "":
                numbers.append(0)
            else:
                numbers.append(int(digits))
        while len(numbers) < 3:
            numbers.append(0)
        return tuple(numbers[:3])

    def _collect_export_refs(self, spec: Dict[str, Any]) -> Tuple[Set[str], Set[str]]:
        if not isinstance(spec, dict):
            try:
                spec = json.loads(spec)
            except Exception:
                spec = {}
        exports = spec.get("exports") or {}
        tools = exports.get("tools") or []
        nodes = exports.get("workflow_nodes") or []
        return set([str(item) for item in tools if item]), set([str(item) for item in nodes if item])

    def _detect_registry_conflicts(
        self,
        *,
        tool_refs: Set[str],
        node_refs: Set[str],
        plugin_name: str,
    ) -> List[Dict[str, Any]]:
        reg = get_registry()
        conflicts: List[Dict[str, Any]] = []

        for tool_ref in sorted(tool_refs):
            found = reg.get_latest(
                kind="tool",
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                name=tool_ref,
            )
            if not found:
                continue
            _, payload = found
            plugin = (payload or {}).get("plugin") or {}
            if plugin and plugin.get("name") == plugin_name:
                continue
            conflicts.append(
                {
                    "kind": "tool",
                    "ref": tool_ref,
                    "existing_plugin": plugin.get("name") if plugin else None,
                }
            )

        for node_ref in sorted(node_refs):
            found = reg.get_latest(
                kind="workflow_node",
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                name=node_ref,
            )
            if not found:
                continue
            _, payload = found
            plugin = (payload or {}).get("plugin") or {}
            if plugin and plugin.get("name") == plugin_name:
                continue
            conflicts.append(
                {
                    "kind": "workflow_node",
                    "ref": node_ref,
                    "existing_plugin": plugin.get("name") if plugin else None,
                }
            )

        return conflicts

    def _check_conflicts(self, *, spec: Dict[str, Any], plugin_name: str) -> None:
        tool_refs, node_refs = self._collect_export_refs(spec)
        conflicts = self._detect_registry_conflicts(
            tool_refs=tool_refs,
            node_refs=node_refs,
            plugin_name=plugin_name,
        )
        if conflicts:
            raise ValidationError(
                "Plugin export conflicts detected",
                {"conflicts": conflicts},
            )

    def _extract_workflow_refs(self, graph: Dict[str, Any]) -> Tuple[Set[str], Set[str]]:
        tool_refs: Set[str] = set()
        node_refs: Set[str] = set()
        if not isinstance(graph, dict):
            try:
                graph = json.loads(graph)
            except Exception:
                return tool_refs, node_refs
        graph_obj = graph.get("graph") or {}
        nodes = graph_obj.get("nodes") or []
        if not isinstance(nodes, list):
            return tool_refs, node_refs
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = node.get("type")
            inputs = node.get("params") or node.get("input") or {}
            if not isinstance(inputs, dict):
                continue
            if node_type == "tool":
                tool_ref = inputs.get("tool_ref") or inputs.get("tool")
                if tool_ref:
                    tool_refs.add(str(tool_ref))
            if node_type == "node":
                node_ref = inputs.get("node_ref") or inputs.get("node")
                if node_ref:
                    node_refs.add(str(node_ref))
        return tool_refs, node_refs

    def _unwrap_db_result(self, result: Any) -> Any:
        if result is None:
            return None
        if isinstance(result, (list, tuple)):
            return result[0] if result else None
        if hasattr(result, "_mapping"):
            try:
                return result[0]
            except Exception:
                return None
        return result

    def _collect_published_workflow_refs(self) -> Tuple[Set[str], Set[str]]:
        tool_refs: Set[str] = set()
        node_refs: Set[str] = set()
        version_ids: Set[str] = set()

        app_query = select(App).where(
            and_(
                App.tenant_id == self.ctx.tenant_id,
                App.workspace_id == self.ctx.workspace_id,
                App.published_version_id != None,  # noqa: E711
            )
        )
        apps = list(self.db.exec(app_query).all())
        for app in apps:
            app_obj = self._unwrap_db_result(app)
            if not app_obj:
                continue
            version_id = getattr(app_obj, "published_version_id", None)
            if version_id:
                version_ids.add(str(version_id))

        market_query = select(AppMarket).where(
            and_(
                AppMarket.tenant_id == self.ctx.tenant_id,
                AppMarket.workspace_id == self.ctx.workspace_id,
            )
        )
        markets = list(self.db.exec(market_query).all())
        for market in markets:
            market_obj = self._unwrap_db_result(market)
            if not market_obj:
                continue
            version_id = getattr(market_obj, "published_version_id", None)
            if version_id:
                version_ids.add(str(version_id))

        for version_id in version_ids:
            version = self.db.exec(
                select(AppVersion).where(
                    and_(
                        AppVersion.id == version_id,
                        AppVersion.tenant_id == self.ctx.tenant_id,
                        AppVersion.workspace_id == self.ctx.workspace_id,
                    )
                )
            ).first()
            version_obj = self._unwrap_db_result(version)
            if not version_obj:
                continue
            if getattr(version_obj, "spec_schema", None) != "workflow.v1":
                continue
            graph_json = getattr(version_obj, "spec_json", None) or {}
            wf_tools, wf_nodes = self._extract_workflow_refs(graph_json)
            tool_refs.update(wf_tools)
            node_refs.update(wf_nodes)
        return tool_refs, node_refs

    def _check_upgrade_compat(self, *, plugin: Plugin, next_spec: Dict[str, Any]) -> None:
        current_spec = plugin.spec_json or {}
        current_tools, current_nodes = self._collect_export_refs(current_spec)
        if not current_tools and not current_nodes:
            return
        next_tools, next_nodes = self._collect_export_refs(next_spec)
        used_tools, used_nodes = self._collect_published_workflow_refs()

        removed_tools = (used_tools & current_tools) - next_tools
        removed_nodes = (used_nodes & current_nodes) - next_nodes
        if removed_tools or removed_nodes:
            raise ValidationError(
                "Plugin upgrade would break published workflows",
                {
                    "removed_tools": sorted(removed_tools),
                    "removed_nodes": sorted(removed_nodes),
                },
            )

    def _check_compatibility(self, spec: Dict[str, Any]) -> None:
        compat = spec.get("compatibility") or {}
        min_v = self._parse_version(compat.get("min_platform_version"))
        max_v = self._parse_version(compat.get("max_platform_version"))
        platform_v = self._parse_version(self.settings.platform_version)
        if not platform_v:
            return
        if min_v and platform_v < min_v:
            raise ValidationError("Plugin requires a newer platform version")
        if max_v and platform_v > max_v:
            raise ValidationError("Plugin requires an older platform version")
        required_features = compat.get("requires_features") or []
        if required_features:
            platform_features = set([str(item) for item in (self.settings.platform_features or [])])
            missing = [feature for feature in required_features if feature not in platform_features]
            if missing:
                raise ValidationError(
                    "Plugin requires unavailable platform features",
                    {"missing_features": missing},
                )

    def _rollout_bucket(self, *, plugin_name: str, version: str) -> int:
        seed = f"{self.ctx.tenant_id}:{self.ctx.workspace_id}:{plugin_name}:{version}"
        digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % 100

    def _check_release_gate(self, *, spec: Dict[str, Any], plugin_name: str) -> None:
        release = spec.get("release") or {}
        channel = (release.get("channel") or "stable").lower()
        rollout = release.get("rollout_percent")
        if rollout is None:
            return
        try:
            rollout_value = float(rollout)
        except (TypeError, ValueError):
            raise ValidationError("Invalid release.rollout_percent value")
        if rollout_value >= 100:
            return
        if rollout_value <= 0:
            raise ValidationError("Plugin rollout is closed", {"channel": channel, "rollout_percent": rollout_value})
        if channel == "stable":
            return
        version = str(spec.get("version") or "")
        bucket = self._rollout_bucket(plugin_name=plugin_name, version=version)
        if bucket >= rollout_value:
            raise ValidationError(
                "Plugin not in rollout cohort",
                {"channel": channel, "rollout_percent": rollout_value},
            )

    def _validate_runtime_manifest(self, manifest: Dict[str, Any]) -> None:
        runtime = (manifest or {}).get("runtime") or {}
        runtime_type = runtime.get("type") or "http"
        if runtime_type != "http":
            raise ValidationError(f"Unsupported plugin runtime type: {runtime_type}")
        base_url = runtime.get("base_url")
        if not base_url:
            raise ValidationError("Plugin manifest missing runtime.base_url")
        parsed = urlparse(base_url)
        host = (parsed.hostname or "").lower()
        if host in ("localhost", "127.0.0.1", "::1") and not self.settings.plugin_runtime_allow_localhost:
            raise ValidationError("Plugin runtime must run out-of-process (localhost not allowed)")

    def _sync_manifest_enabled(self, *, plugin_name: str, version: str, enabled: bool) -> None:
        """Best-effort: keep filesystem manifest enabled flag in sync."""
        install_dir = self._install_dir_for(plugin_name=plugin_name, version=version)
        manifest_path = install_dir / "manifest.json"
        if not manifest_path.exists():
            return
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["enabled"] = bool(enabled)
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            # Do not fail requests on filesystem issues
            return

    def _sync_registry_for_plugin(self, *, plugin_name: str, version: str, enabled: bool) -> None:
        """Sync in-process registry for a plugin version (tools/nodes + plugin record)."""
        reg = get_registry()

        # remove all tool artifacts belonging to this plugin+version in this scope
        items = reg.list(kind="tool", tenant_id=self.ctx.tenant_id, workspace_id=self.ctx.workspace_id)
        for key, payload in items:
            plugin = (payload or {}).get("plugin") or {}
            if plugin.get("name") == plugin_name and plugin.get("version") == version:
                reg.unregister(key)

        # remove plugin artifact
        plugin_items = reg.list(
            kind="plugin",
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            name=plugin_name,
        )
        for key, _ in plugin_items:
            if key.version == version:
                reg.unregister(key)

        # remove all workflow node artifacts belonging to this plugin+version in this scope
        node_items = reg.list(kind="workflow_node", tenant_id=self.ctx.tenant_id, workspace_id=self.ctx.workspace_id)
        for key, payload in node_items:
            plugin = (payload or {}).get("plugin") or {}
            if plugin.get("name") == plugin_name and plugin.get("version") == version:
                reg.unregister(key)

        if enabled:
            # reload from filesystem (best-effort)
            PluginRuntimeLoader().load_all()

    @rbac_guard(RESOURCE_PLUGIN, "create", resource_id_resolver=_resolve_plugin_create_id)
    async def create_plugin(self, plugin_in: PluginCreate) -> Plugin:
        """Create a new plugin.
        
        Args:
            plugin_in: Plugin creation schema.
            
        Returns:
            Created Plugin instance.
            
        Raises:
            ValidationError: If plugin name and version combination already exists.
        """
        # Check if name and version combination already exists
        existing = self.plugin_repo.get_by_name_version(plugin_in.name, plugin_in.version)
        if existing:
            raise ValidationError(
                f"Plugin '{plugin_in.name}' version '{plugin_in.version}' already exists"
            )
        
        plugin = Plugin(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            name=plugin_in.name,
            version=plugin_in.version,
            description=plugin_in.description,
            spec_json=plugin_in.spec_json,
            manifest_json=plugin_in.manifest_json,
            metadata_json=plugin_in.metadata_json,
            published=False,
            created_by=self.ctx.user_id,
        )
        
        plugin = self.plugin_repo.create(plugin)
        logger.info(
            "plugin.create",
            extra={
                "plugin_name": plugin.name,
                "version": plugin.version,
                "tenant_id": self.ctx.tenant_id,
                "workspace_id": self.ctx.workspace_id,
            },
        )
        return plugin
    
    @rbac_guard(RESOURCE_PLUGIN, "read", resource_id_arg="plugin_id")
    async def get_plugin(self, plugin_id: str) -> Plugin:
        """Get plugin by ID.
        
        Args:
            plugin_id: Plugin ID.
            
        Returns:
            Plugin instance.
            
        Raises:
            NotFoundError: If plugin not found.
        """
        plugin = self.plugin_repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundError(f"Plugin not found: {plugin_id}")
        return plugin
    


    @workspace_guard("read")
    async def list_plugins(
        self,
        published_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Plugin]:
        """List plugins.
        
        Args:
            published_only: Only return published plugins.
            limit: Maximum number of plugins.
            offset: Offset for pagination.
            
        Returns:
            List of Plugin instances.
        """
        return self.plugin_repo.list(published_only=published_only, limit=limit, offset=offset)
    
    @rbac_guard(RESOURCE_PLUGIN, "update", resource_id_arg="plugin_id")
    async def update_plugin(self, plugin_id: str, plugin_in: PluginUpdate) -> Plugin:
        """Update plugin.
        
        Args:
            plugin_id: Plugin ID.
            plugin_in: Plugin update schema.
            
        Returns:
            Updated Plugin instance.
            
        Raises:
            NotFoundError: If plugin not found.
        """
        plugin = await self.get_plugin(plugin_id)
        
        if plugin_in.description is not None:
            plugin.description = plugin_in.description
        
        if plugin_in.spec_json is not None:
            plugin.spec_json = plugin_in.spec_json
        
        if plugin_in.manifest_json is not None:
            plugin.manifest_json = plugin_in.manifest_json
        
        if plugin_in.metadata_json is not None:
            plugin.metadata_json = plugin_in.metadata_json
        
        if plugin_in.published is not None:
            plugin.published = plugin_in.published
        
        plugin.updated_at = utc_now()
        
        self.db.commit()
        self.db.refresh(plugin)
        logger.info(
            "plugin.update",
            extra={
                "plugin_id": plugin_id,
                "tenant_id": self.ctx.tenant_id,
                "workspace_id": self.ctx.workspace_id,
            },
        )
        return plugin
    
    @rbac_guard(RESOURCE_PLUGIN, "delete", resource_id_arg="plugin_id")
    async def delete_plugin(self, plugin_id: str) -> None:
        """Delete plugin.
        
        Args:
            plugin_id: Plugin ID.
            
        Raises:
            NotFoundError: If plugin not found.
        """
        plugin = await self.get_plugin(plugin_id)
        
        # Delete associated installations
        installations = self.installation_repo.list_by_workspace(limit=1000, offset=0)
        for installation in installations:
            if installation.plugin_id == plugin_id:
                self.db.delete(installation)
        
        self.db.delete(plugin)
        self.db.commit()
        logger.info(
            "plugin.delete",
            extra={
                "plugin_id": plugin_id,
                "tenant_id": self.ctx.tenant_id,
                "workspace_id": self.ctx.workspace_id,
            },
        )
    
    @rbac_guard(RESOURCE_PLUGIN, "update", resource_id_arg="plugin_id")
    async def install_plugin(self, plugin_id: str, install_request: PluginInstallRequest) -> PluginInstallation:
        """Install a plugin.
        
        Args:
            plugin_id: Plugin ID.
            install_request: Installation request.
            
        Returns:
            Created PluginInstallation instance.
            
        Raises:
            NotFoundError: If plugin not found.
            ValidationError: If plugin is already installed.
        """
        plugin = await self.get_plugin(plugin_id)
        
        # Check if already installed
        existing = self.installation_repo.get_by_plugin(plugin_id)
        if existing:
            raise ValidationError(f"Plugin '{plugin.name}' is already installed")
        
        # Create installation
        installation = PluginInstallation(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            plugin_id=plugin_id,
            installed_by=self.ctx.user_id,
            config_json=install_request.config_json,
        )
        
        installation = self.installation_repo.create(installation)
        
        # Update plugin installed_count
        plugin.installed_count += 1
        self.db.commit()
        self.db.refresh(plugin)

        logger.info(
            "plugin.install_record",
            extra={
                "plugin_id": plugin_id,
                "tenant_id": self.ctx.tenant_id,
                "workspace_id": self.ctx.workspace_id,
            },
        )
        
        return installation

    @rbac_guard(RESOURCE_PLUGIN, "update", resource_id_arg="plugin_id")
    async def install_plugin_package(
        self,
        plugin_id: str,
        package_bytes: bytes,
        *,
        expected_sha256: Optional[str] = None,
    ) -> dict:
        """Install plugin package bytes into filesystem and register into runtime registry.

        This does NOT change DB schema. It will:
        1) validate plugin exists
        2) install package into plugins_dir
        3) mark installation record (creates if absent)

        Returns:
            dict with install_dir, sha256, manifest, spec
        """
        plugin = await self.get_plugin(plugin_id)
        manifest, spec = self.installer.inspect_package(package_bytes)
        spec_name = spec.get("name")
        spec_version = spec.get("version")
        if spec_name and spec_name != plugin.name:
            raise ValidationError("Plugin package name mismatch")
        if spec_version and spec_version != plugin.version:
            raise ValidationError("Plugin package version mismatch")
        self._check_compatibility(spec)
        self._check_release_gate(spec=spec, plugin_name=plugin.name)
        self._validate_runtime_manifest(manifest)
        self._check_conflicts(spec=spec, plugin_name=plugin.name)

        paths = self.installer.install_from_bytes(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            plugin_name=plugin.name,
            version=plugin.version,
            package_bytes=package_bytes,
            expected_sha256=expected_sha256,
        )

        # ensure installation row exists
        existing = self.installation_repo.get_by_plugin(plugin_id)
        if not existing:
            installation = PluginInstallation(
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                plugin_id=plugin_id,
                installed_by=self.ctx.user_id,
                config_json={"enabled": True},
            )
            self.installation_repo.create(installation)
            plugin.installed_count += 1
            self.db.commit()
            self.db.refresh(plugin)
        else:
            cfg = existing.config_json or {}
            cfg.setdefault("enabled", True)
            existing.config_json = cfg
            self.installation_repo.update(existing)
            self.db.commit()

        plugin.spec_json = spec
        plugin.manifest_json = manifest
        plugin.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(plugin)

        return {
            "install_dir": str(paths.install_dir),
            "package_path": str(paths.package_path),
            "manifest_path": str(paths.manifest_path),
            "spec_path": str(paths.spec_path),
        }

    @rbac_guard(RESOURCE_PLUGIN, "delete", resource_id_arg="plugin_id")
    async def uninstall_plugin(self, plugin_id: str) -> None:
        """Uninstall a plugin from this workspace."""
        plugin = await self.get_plugin(plugin_id)

        installation = self.installation_repo.get_by_plugin(plugin_id)
        if installation:
            self.db.delete(installation)
            if plugin.installed_count > 0:
                plugin.installed_count -= 1
            plugin.updated_at = utc_now()
            self.db.commit()

        self._sync_registry_for_plugin(plugin_name=plugin.name, version=plugin.version, enabled=False)
        self._remove_plugin_files(plugin_name=plugin.name, version=plugin.version)

        logger.info(
            "plugin.uninstall",
            extra={
                "plugin_id": plugin_id,
                "tenant_id": self.ctx.tenant_id,
                "workspace_id": self.ctx.workspace_id,
            },
        )

    @rbac_guard(RESOURCE_PLUGIN, "update", resource_id_arg="plugin_id")
    async def upgrade_plugin_package(
        self,
        plugin_id: str,
        package_bytes: bytes,
        *,
        expected_sha256: Optional[str] = None,
    ) -> dict:
        """Upgrade an installed plugin by replacing its package/version."""
        plugin = await self.get_plugin(plugin_id)

        manifest, spec = self.installer.inspect_package(package_bytes)
        spec_name = spec.get("name")
        spec_version = spec.get("version")
        if spec_name and spec_name != plugin.name:
            raise ValidationError("Plugin package name mismatch")
        if not spec_version:
            raise ValidationError("Plugin package missing version")
        self._check_compatibility(spec)
        self._check_release_gate(spec=spec, plugin_name=plugin.name)
        self._validate_runtime_manifest(manifest)
        self._check_conflicts(spec=spec, plugin_name=plugin.name)
        self._check_upgrade_compat(plugin=plugin, next_spec=spec)

        old_version = plugin.version
        plugin.version = spec_version
        plugin.spec_json = spec
        plugin.manifest_json = manifest
        plugin.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(plugin)

        paths = self.installer.install_from_bytes(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            plugin_name=plugin.name,
            version=spec_version,
            package_bytes=package_bytes,
            expected_sha256=expected_sha256,
        )

        if old_version != spec_version:
            self._sync_registry_for_plugin(plugin_name=plugin.name, version=old_version, enabled=False)
            self._remove_plugin_files(plugin_name=plugin.name, version=old_version)

        logger.info(
            "plugin.upgrade",
            extra={
                "plugin_id": plugin_id,
                "old_version": old_version,
                "new_version": spec_version,
                "tenant_id": self.ctx.tenant_id,
                "workspace_id": self.ctx.workspace_id,
            },
        )

        return {
            "install_dir": str(paths.install_dir),
            "package_path": str(paths.package_path),
            "manifest_path": str(paths.manifest_path),
            "spec_path": str(paths.spec_path),
        }

    @rbac_guard(RESOURCE_PLUGIN, "update", resource_id_arg="plugin_id")
    async def set_plugin_enabled(self, plugin_id: str, enabled: bool) -> PluginInstallation:
        """Enable/disable a plugin installation in this workspace.

        State is stored in:
        - DB: PluginInstallation.config_json["enabled"]
        - FS: <install_dir>/manifest.json["enabled"] (for restart-safe runtime loader)
        """
        plugin = await self.get_plugin(plugin_id)

        installation = self.installation_repo.get_by_plugin(plugin_id)
        if not installation:
            raise NotFoundError("Plugin is not installed.")

        cfg = installation.config_json or {}
        cfg["enabled"] = bool(enabled)
        installation.config_json = cfg
        installation = self.installation_repo.update(installation)
        self.db.commit()
        self.db.refresh(installation)

        # keep filesystem manifest in-sync for restart-safe loader
        self._sync_manifest_enabled(plugin_name=plugin.name, version=plugin.version, enabled=bool(enabled))

        # sync runtime registry (tools + plugin record)
        self._sync_registry_for_plugin(plugin_name=plugin.name, version=plugin.version, enabled=bool(enabled))

        logger.info(
            "plugin.enabled",
            extra={
                "plugin_id": plugin_id,
                "enabled": bool(enabled),
                "tenant_id": self.ctx.tenant_id,
                "workspace_id": self.ctx.workspace_id,
            },
        )

        return installation
