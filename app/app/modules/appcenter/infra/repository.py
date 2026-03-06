""" repository

AppCenter domain repository.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, select

from app.kernel.contracts.context import RequestContext
from app.infra.db.pagination import PaginatedResult, paginate_query
from app.modules.appcenter.domain.models import App, AppVersion, AppMarket, AppInstallation


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
        query = select(App).where(
            and_(
                App.id == app_id,
                App.tenant_id == self.ctx.tenant_id,
                App.workspace_id == self.ctx.workspace_id,
            )
        )
        result = self.db.exec(query).first()
        return result if isinstance(result, App) else result[0] if result else None
    
    def list(
        self,
        page_size: int = 20,
        page_token: Optional[str] = None,
        search: Optional[str] = None,
        app_type: Optional[str] = None,
        status: Optional[str] = None,
        visibility: Optional[str] = None,
    ) -> PaginatedResult[App]:
        """List apps.
        
        Args:
            page_size: Page size.
            page_token: Page token.
            search: Optional search query.
            
        Returns:
            Paginated apps.
        """
        query = select(App).where(
            and_(
                App.tenant_id == self.ctx.tenant_id,
                App.workspace_id == self.ctx.workspace_id,
            )
        )
        
        if search:
            query = query.where(
                or_(
                    App.name.ilike(f"%{search}%"),
                    App.description.ilike(f"%{search}%"),
                )
            )
        if app_type:
            query = query.where(App.type == app_type.upper())
        if status:
            query = query.where(App.status == status)
        if visibility:
            query = query.where(App.visibility == visibility)
        
        query = query.order_by(desc(App.updated_at))
        
        return paginate_query(query, page_size, page_token, exec_fn=self.db.exec)
    
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
        query = select(AppVersion).where(
            and_(
                AppVersion.id == version_id,
                AppVersion.tenant_id == self.ctx.tenant_id,
                AppVersion.workspace_id == self.ctx.workspace_id,
            )
        )
        result = self.db.exec(query).first()
        return result if isinstance(result, AppVersion) else result[0] if result else None
    
    def list_by_app(self, app_id: str) -> List[AppVersion]:
        """List versions for an app.
        
        Args:
            app_id: App ID.
            
        Returns:
            List of versions.
        """
        query = select(AppVersion).where(
            and_(
                AppVersion.app_id == app_id,
                AppVersion.tenant_id == self.ctx.tenant_id,
                AppVersion.workspace_id == self.ctx.workspace_id,
            )
        ).order_by(desc(AppVersion.created_at))
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, AppVersion) else item[0] for item in results]


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
        query = select(AppMarket).join(App).where(App.is_public == True)
        
        if category:
            query = query.where(App.category == category)
        
        if featured is not None:
            query = query.where(AppMarket.featured == featured)
        
        query = query.order_by(desc(AppMarket.published_at))
        
        return paginate_query(query, page_size, page_token, exec_fn=self.db.exec)


class AppInstallationRepository:
    """Repository for AppInstallation operations."""

    def __init__(self, db: Session, ctx: RequestContext):
        self.db = db
        self.ctx = ctx

    def create(self, installation: AppInstallation) -> AppInstallation:
        installation.tenant_id = self.ctx.tenant_id
        installation.workspace_id = self.ctx.workspace_id
        installation.installed_by = self.ctx.user_id
        self.db.add(installation)
        self.db.commit()
        self.db.refresh(installation)
        return installation

    def get_by_id(self, installation_id: str) -> Optional[AppInstallation]:
        query = select(AppInstallation).where(
            and_(
                AppInstallation.id == installation_id,
                AppInstallation.tenant_id == self.ctx.tenant_id,
                AppInstallation.workspace_id == self.ctx.workspace_id,
            )
        )
        result = self.db.exec(query).first()
        return result if isinstance(result, AppInstallation) else result[0] if result else None

    def get_by_app(self, app_id: str) -> Optional[AppInstallation]:
        query = select(AppInstallation).where(
            and_(
                AppInstallation.app_id == app_id,
                AppInstallation.tenant_id == self.ctx.tenant_id,
                AppInstallation.workspace_id == self.ctx.workspace_id,
            )
        )
        result = self.db.exec(query).first()
        return result if isinstance(result, AppInstallation) else result[0] if result else None

    def list_by_workspace(self) -> List[AppInstallation]:
        query = select(AppInstallation).where(
            and_(
                AppInstallation.tenant_id == self.ctx.tenant_id,
                AppInstallation.workspace_id == self.ctx.workspace_id,
            )
        ).order_by(desc(AppInstallation.created_at))
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, AppInstallation) else item[0] for item in results]

    def update(self, installation: AppInstallation) -> AppInstallation:
        self.db.commit()
        self.db.refresh(installation)
        return installation

    def delete(self, installation_id: str) -> None:
        installation = self.get_by_id(installation_id)
        if installation:
            self.db.delete(installation)
            self.db.commit()
