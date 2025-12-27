""" repository

AppCenter domain repository.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from app.kernel.contracts.context import RequestContext
from app.kernel.db.pagination import PaginatedResult, paginate_query
from app.modules.domains.appcenter.models import App, AppVersion, AppMarket


class AppRepository:
    """Repository for App operations."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize repository.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        self.db = db
        self.ctx = ctx
    
    def create(self, app: App) -> App:
        """Create app.
        
        Args:
            app: App instance.
            
        Returns:
            Created app.
        """
        app.tenant_id = self.ctx.tenant_id
        app.workspace_id = self.ctx.workspace_id
        app.created_by = self.ctx.user_id
        self.db.add(app)
        self.db.commit()
        self.db.refresh(app)
        return app
    
    def get_by_id(self, app_id: str) -> Optional[App]:
        """Get app by ID.
        
        Args:
            app_id: App ID.
            
        Returns:
            App instance or None.
        """
        return self.db.query(App).filter(
            and_(
                App.id == app_id,
                App.tenant_id == self.ctx.tenant_id,
                App.workspace_id == self.ctx.workspace_id,
            )
        ).first()
    
    def list(
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
        query = self.db.query(App).filter(
            and_(
                App.tenant_id == self.ctx.tenant_id,
                App.workspace_id == self.ctx.workspace_id,
            )
        )
        
        if search:
            query = query.filter(
                or_(
                    App.name.ilike(f"%{search}%"),
                    App.description.ilike(f"%{search}%"),
                )
            )
        
        query = query.order_by(desc(App.updated_at))
        
        return paginate_query(query, page_size, page_token)
    
    def update(self, app: App) -> App:
        """Update app.
        
        Args:
            app: App instance.
            
        Returns:
            Updated app.
        """
        self.db.commit()
        self.db.refresh(app)
        return app
    
    def delete(self, app_id: str) -> None:
        """Delete app.
        
        Args:
            app_id: App ID.
        """
        app = self.get_by_id(app_id)
        if app:
            self.db.delete(app)
            self.db.commit()


class AppVersionRepository:
    """Repository for AppVersion operations."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize repository.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        self.db = db
        self.ctx = ctx
    
    def create(self, version: AppVersion) -> AppVersion:
        """Create app version.
        
        Args:
            version: AppVersion instance.
            
        Returns:
            Created version.
        """
        version.tenant_id = self.ctx.tenant_id
        version.workspace_id = self.ctx.workspace_id
        version.created_by = self.ctx.user_id
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version
    
    def get_by_id(self, version_id: str) -> Optional[AppVersion]:
        """Get version by ID.
        
        Args:
            version_id: Version ID.
            
        Returns:
            AppVersion instance or None.
        """
        return self.db.query(AppVersion).filter(
            and_(
                AppVersion.id == version_id,
                AppVersion.tenant_id == self.ctx.tenant_id,
                AppVersion.workspace_id == self.ctx.workspace_id,
            )
        ).first()
    
    def list_by_app(self, app_id: str) -> List[AppVersion]:
        """List versions for an app.
        
        Args:
            app_id: App ID.
            
        Returns:
            List of versions.
        """
        return self.db.query(AppVersion).filter(
            and_(
                AppVersion.app_id == app_id,
                AppVersion.tenant_id == self.ctx.tenant_id,
                AppVersion.workspace_id == self.ctx.workspace_id,
            )
        ).order_by(desc(AppVersion.created_at)).all()


class AppMarketRepository:
    """Repository for AppMarket operations."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize repository.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        self.db = db
        self.ctx = ctx
    
    def list_public(
        self,
        page_size: int = 20,
        page_token: Optional[str] = None,
        category: Optional[str] = None,
        featured: Optional[bool] = None,
    ) -> PaginatedResult[AppMarket]:
        """List public apps in marketplace.
        
        Args:
            page_size: Page size.
            page_token: Page token.
            category: Optional category filter.
            featured: Optional featured filter.
            
        Returns:
            Paginated market apps.
        """
        query = self.db.query(AppMarket).join(App).filter(
            App.is_public == True
        )
        
        if category:
            query = query.filter(App.category == category)
        
        if featured is not None:
            query = query.filter(AppMarket.featured == featured)
        
        query = query.order_by(desc(AppMarket.published_at))
        
        return paginate_query(query, page_size, page_token)

