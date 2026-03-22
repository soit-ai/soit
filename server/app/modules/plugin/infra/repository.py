"""Plugin domain repository."""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc

from app.infra.db.repository import Repository
from app.kernel.contracts.context import RequestContext
from app.modules.plugin.domain.models import Plugin, PluginInstallation


class PluginRepository(Repository[Plugin]):
    """Repository for Plugin model."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize plugin repository.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(Plugin, db, ctx)
    
    def get_by_name_version(self, name: str, version: str) -> Optional[Plugin]:
        """Get plugin by name and version.
        
        Args:
            name: Plugin name.
            version: Plugin version.
            
        Returns:
            Plugin instance or None if not found.
        """
        query = select(Plugin).where(
            and_(
                Plugin.tenant_id == self.ctx.tenant_id,
                Plugin.workspace_id == self.ctx.workspace_id,
                Plugin.name == name,
                Plugin.version == version,
            )
        )
        return self.db.exec(query).first()
    
    def list(
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
        query = select(Plugin).where(
            and_(
                Plugin.tenant_id == self.ctx.tenant_id,
                Plugin.workspace_id == self.ctx.workspace_id,
            )
        )
        
        if published_only:
            query = query.where(Plugin.published == True)
        
        query = query.order_by(desc(Plugin.created_at)).offset(offset).limit(limit)
        
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)


class PluginInstallationRepository(Repository[PluginInstallation]):
    """Repository for PluginInstallation model."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize plugin installation repository.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(PluginInstallation, db, ctx)
    
    def create(self, installation: PluginInstallation) -> PluginInstallation:
        """Create a new installation.
        
        Args:
            installation: PluginInstallation instance.
            
        Returns:
            Created PluginInstallation instance.
        """
        self.db.add(installation)
        self.db.commit()
        self.db.refresh(installation)
        return installation
    
    def get_by_plugin(self, plugin_id: str) -> Optional[PluginInstallation]:
        """Get installation by plugin ID.
        
        Args:
            plugin_id: Plugin ID.
            
        Returns:
            PluginInstallation instance or None if not found.
        """
        query = select(PluginInstallation).where(
            and_(
                PluginInstallation.tenant_id == self.ctx.tenant_id,
                PluginInstallation.workspace_id == self.ctx.workspace_id,
                PluginInstallation.plugin_id == plugin_id,
            )
        )
        result = self.db.exec(query).first()
        return self._unwrap_result(result)
    
    def list_by_workspace(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> List[PluginInstallation]:
        """List installations in workspace.
        
        Args:
            limit: Maximum number of installations.
            offset: Offset for pagination.
            
        Returns:
            List of PluginInstallation instances.
        """
        query = select(PluginInstallation).where(
            and_(
                PluginInstallation.tenant_id == self.ctx.tenant_id,
                PluginInstallation.workspace_id == self.ctx.workspace_id,
            )
        ).order_by(desc(PluginInstallation.created_at)).offset(offset).limit(limit)
        
        return list(self.db.exec(query).all())
