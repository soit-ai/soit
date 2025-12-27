""" service

PluginMarket domain service.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now
from app.modules.domains.pluginmarket.models import Plugin, PluginInstallation
from app.modules.domains.pluginmarket.repository import (
    PluginRepository,
    PluginInstallationRepository,
)
from app.modules.domains.pluginmarket.schemas import PluginCreate, PluginUpdate, PluginInstallRequest


class PluginMarketService:
    """PluginMarket domain service."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize plugin market service.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        self.db = db
        self.ctx = ctx
        self.plugin_repo = PluginRepository(db, ctx)
        self.installation_repo = PluginInstallationRepository(db, ctx)
    
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
