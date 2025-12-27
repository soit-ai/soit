""" service

AppCenter domain service.
"""

from typing import Optional, List
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.db.pagination import PaginatedResult
from app.kernel.identity.rbac import require_workspace_write, require_workspace_read
from app.modules.domains.appcenter.models import App, AppVersion, AppMarket
from app.modules.domains.appcenter.repository import (
    AppRepository,
    AppVersionRepository,
    AppMarketRepository,
)
from app.modules.domains.appcenter.schemas import (
    AppCreate,
    AppUpdate,
    AppVersionCreate,
    AppPublish,
)


class AppService:
    """App service."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize service.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        self.db = db
        self.ctx = ctx
        self.app_repo = AppRepository(db, ctx)
        self.version_repo = AppVersionRepository(db, ctx)
        self.market_repo = AppMarketRepository(db, ctx)
    
    def create_app(self, data: AppCreate) -> App:
        """Create app.
        
        Args:
            data: App creation data.
            
        Returns:
            Created app.
        """
        require_workspace_write(self.ctx)
        
        app = App(
            name=data.name,
            description=data.description,
            icon_url=data.icon_url,
            category=data.category,
            tags=data.tags,
        )
        return self.app_repo.create(app)
    
    def get_app(self, app_id: str) -> Optional[App]:
        """Get app by ID.
        
        Args:
            app_id: App ID.
            
        Returns:
            App instance or None.
        """
        require_workspace_read(self.ctx)
        return self.app_repo.get_by_id(app_id)
    
    def list_apps(
        self,
        page_size: int = 20,
        page_token: Optional[str] = None,
        search: Optional[str] = None,
    ) -> PaginatedResult[App]:
        """List apps.
        
        Args:
            page_size: Page size.
            page_token: Page token.
            search: Optional search query.
            
        Returns:
            Paginated apps.
        """
        require_workspace_read(self.ctx)
        return self.app_repo.list(page_size, page_token, search)
    
    def update_app(self, app_id: str, data: AppUpdate) -> Optional[App]:
        """Update app.
        
        Args:
            app_id: App ID.
            data: App update data.
            
        Returns:
            Updated app or None.
        """
        require_workspace_write(self.ctx)
        
        app = self.app_repo.get_by_id(app_id)
        if not app:
            return None
        
        if data.name is not None:
            app.name = data.name
        if data.description is not None:
            app.description = data.description
        if data.icon_url is not None:
            app.icon_url = data.icon_url
        if data.category is not None:
            app.category = data.category
        if data.tags is not None:
            app.tags = data.tags
        if data.is_public is not None:
            app.is_public = data.is_public
        
        return self.app_repo.update(app)
    
    def delete_app(self, app_id: str) -> bool:
        """Delete app.
        
        Args:
            app_id: App ID.
            
        Returns:
            True if deleted.
        """
        require_workspace_write(self.ctx)
        
        app = self.app_repo.get_by_id(app_id)
        if not app:
            return False
        
        self.app_repo.delete(app_id)
        return True
    
    def create_version(self, app_id: str, data: AppVersionCreate) -> Optional[AppVersion]:
        """Create app version.
        
        Args:
            app_id: App ID.
            data: Version creation data.
            
        Returns:
            Created version or None.
        """
        require_workspace_write(self.ctx)
        
        app = self.app_repo.get_by_id(app_id)
        if not app:
            return None
        
        version = AppVersion(
            app_id=app_id,
            version=data.version,
            manifest_json=data.manifest_json,
            workflow_version_id=data.workflow_version_id,
            changelog=data.changelog,
        )
        version = self.version_repo.create(version)
        
        # Update app current_version_id
        app.current_version_id = version.id
        self.app_repo.update(app)
        
        return version
    
    def list_versions(self, app_id: str) -> List[AppVersion]:
        """List app versions.
        
        Args:
            app_id: App ID.
            
        Returns:
            List of versions.
        """
        require_workspace_read(self.ctx)
        return self.version_repo.list_by_app(app_id)
    
    def publish_app(self, app_id: str, data: AppPublish) -> Optional[AppMarket]:
        """Publish app to marketplace.
        
        Args:
            app_id: App ID.
            data: Publish data.
            
        Returns:
            Market listing or None.
        """
        require_workspace_write(self.ctx)
        
        app = self.app_repo.get_by_id(app_id)
        if not app:
            return None
        
        version = self.version_repo.get_by_id(data.version_id)
        if not version or version.app_id != app_id:
            return None
        
        # Update app published_version_id
        app.published_version_id = data.version_id
        app.is_public = True
        self.app_repo.update(app)
        
        # Create or update market listing
        market = self.db.query(AppMarket).filter(
            AppMarket.app_id == app_id
        ).first()
        
        if market:
            market.published_version_id = data.version_id
            market.featured = data.featured
            self.db.commit()
            self.db.refresh(market)
        else:
            market = AppMarket(
                app_id=app_id,
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                published_version_id=data.version_id,
                featured=data.featured,
            )
            self.db.add(market)
            self.db.commit()
            self.db.refresh(market)
        
        return market
    
    def list_marketplace(
        self,
        page_size: int = 20,
        page_token: Optional[str] = None,
        category: Optional[str] = None,
        featured: Optional[bool] = None,
    ) -> PaginatedResult[AppMarket]:
        """List apps in marketplace.
        
        Args:
            page_size: Page size.
            page_token: Page token.
            category: Optional category filter.
            featured: Optional featured filter.
            
        Returns:
            Paginated market apps.
        """
        # Marketplace is public, no permission check needed
        return self.market_repo.list_public(page_size, page_token, category, featured)

