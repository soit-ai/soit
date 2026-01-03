""" service

PluginMarket domain service.
"""

import json
from typing import Optional, List, Dict, Any
from pathlib import Path
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now
from app.kernel.registry.deps import get_registry
from app.modules.pluginmarket.runtime.loader import PluginRuntimeLoader
from app.modules.pluginmarket.domain.models import Plugin, PluginInstallation
from app.modules.pluginmarket.application.ports import PluginRepositoryPort, PluginInstallationRepositoryPort
from app.modules.pluginmarket.application.schemas import PluginCreate, PluginUpdate, PluginInstallRequest
from app.modules.pluginmarket.infrastructure.installer import PluginInstaller


class PluginMarketService:
    """PluginMarket domain service."""
    
    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        plugin_repo: PluginRepositoryPort,
        installation_repo: PluginInstallationRepositoryPort,
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


def _install_dir_for(self, *, plugin_name: str, version: str) -> Path:
    root = Path(self.settings.plugins_dir).resolve()
    return root / "installed" / self.ctx.tenant_id / self.ctx.workspace_id / plugin_name / version

def _sync_manifest_enabled(self, *, plugin_name: str, version: str, enabled: bool) -> None:
    install_dir = self._install_dir_for(plugin_name=plugin_name, version=version)
    manifest_path = install_dir / "manifest.json"
    if not manifest_path.exists():
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["enabled"] = bool(enabled)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        return

def _sync_registry_for_plugin(self, *, plugin_name: str, version: str, enabled: bool) -> None:
    reg = get_registry()
    # remove all tool artifacts belonging to this plugin+version in this scope
    items = reg.list(kind="tool", tenant_id=self.ctx.tenant_id, workspace_id=self.ctx.workspace_id)
    for key, payload in items:
        plugin = (payload or {}).get("plugin") or {}
        if plugin.get("name") == plugin_name and plugin.get("version") == version:
            reg.unregister(key)

    # remove plugin artifact
    plugin_items = reg.list(kind="plugin", tenant_id=self.ctx.tenant_id, workspace_id=self.ctx.workspace_id, name=plugin_name)
    for key, _ in plugin_items:
        if key.version == version:
            reg.unregister(key)

    if enabled:
        # reload from filesystem (best-effort)
        PluginRuntimeLoader().load_all()

    def create_plugin(self, plugin_in: PluginCreate) -> Plugin:
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
        
        return self.plugin_repo.create(plugin)
    
    def get_plugin(self, plugin_id: str) -> Plugin:
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
    


    def list_plugins(
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
    
    def update_plugin(self, plugin_id: str, plugin_in: PluginUpdate) -> Plugin:
        """Update plugin.
        
        Args:
            plugin_id: Plugin ID.
            plugin_in: Plugin update schema.
            
        Returns:
            Updated Plugin instance.
            
        Raises:
            NotFoundError: If plugin not found.
        """
        plugin = self.get_plugin(plugin_id)
        
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
        return plugin
    
    def delete_plugin(self, plugin_id: str) -> None:
        """Delete plugin.
        
        Args:
            plugin_id: Plugin ID.
            
        Raises:
            NotFoundError: If plugin not found.
        """
        plugin = self.get_plugin(plugin_id)
        
        # Delete associated installations
        installations = self.installation_repo.list_by_workspace(limit=1000, offset=0)
        for installation in installations:
            if installation.plugin_id == plugin_id:
                self.db.delete(installation)
        
        self.db.delete(plugin)
        self.db.commit()
    
    def install_plugin(self, plugin_id: str, install_request: PluginInstallRequest) -> PluginInstallation:
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
        plugin = self.get_plugin(plugin_id)
        
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
        
        return installation

    def install_plugin_package(
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
        plugin = self.get_plugin(plugin_id)

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

        return {
            "install_dir": str(paths.install_dir),
            "package_path": str(paths.package_path),
            "manifest_path": str(paths.manifest_path),
            "spec_path": str(paths.spec_path),
        }

    def set_plugin_enabled(self, plugin_id: str, enabled: bool) -> PluginInstallation:
        """Enable/disable a plugin installation in this workspace.

        State is stored in:
        - DB: PluginInstallation.config_json["enabled"]
        - FS: <install_dir>/manifest.json["enabled"] (for restart-safe runtime loader)
        """
        plugin = self.get_plugin(plugin_id)

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

        return installation

