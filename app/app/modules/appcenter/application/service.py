""" service

AppCenter domain service.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.commons.serialization import checksum_json
from app.infra.db.pagination import PaginatedResult
from app.kernel.identity.guard import rbac_guard, workspace_guard
from app.kernel.identity.permissions import RESOURCE_APP
from app.modules.appcenter.domain.models import (
    App,
    AppVersion,
    AppMarket,
    AppInstallation,
    AppComponent,
    AppComponentEdge,
    AppVersionRef,
)
from app.modules.appcenter.application.ports import (
    AppRepositoryPort,
    AppVersionRepositoryPort,
    AppMarketRepositoryPort,
    AppInstallationRepositoryPort,
)
from app.modules.appcenter.application.schemas import (
    AppCreate,
    AppUpdate,
    AppVersionCreate,
    AppPublish,
    AppInstallRequest,
    AppCloneRequest,
    AppImportRequest,
)


class AppService:
    """App service."""
    
    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        app_repo: AppRepositoryPort,
        app_version_repo: AppVersionRepositoryPort,
        app_market_repo: AppMarketRepositoryPort,
        app_installation_repo: AppInstallationRepositoryPort,
    ):
        """Initialize service.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        self.db = db
        self.ctx = ctx
        self.app_repo = app_repo
        self.app_version_repo = app_version_repo
        self.app_market_repo = app_market_repo
        self.app_installation_repo = app_installation_repo

    def _resolve_app_create_id(self, data: AppCreate, **kwargs) -> str:
        """Resolve app id for create RBAC checks."""
        return data.name or f"new:{self.ctx.workspace_id}"

    @rbac_guard(RESOURCE_APP, "create", resource_id_resolver=_resolve_app_create_id)
    async def create_app(self, data: AppCreate) -> App:
        """Create app.
        
        Args:
            data: App creation data.
            
        Returns:
            Created app.
        """
        app = App(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            type=(data.type or "WORKFLOW").upper(),
            status=data.status or "active",
            visibility=data.visibility or "private",
            name=data.name,
            description=data.description,
            icon_url=data.icon_url,
            category=data.category,
            tags=data.tags,
            created_by=self.ctx.user_id,
        )
        return self.app_repo.create(app)
    
    @rbac_guard(RESOURCE_APP, "read", resource_id_arg="app_id")
    async def get_app(self, app_id: str) -> Optional[App]:
        """Get app by ID.
        
        Args:
            app_id: App ID.
            
        Returns:
            App instance or None.
        """
        return self.app_repo.get_by_id(app_id)
    
    @workspace_guard("read")
    async def list_apps(
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
        return self.app_repo.list(
            page_size=page_size,
            page_token=page_token,
            search=search,
            app_type=app_type,
            status=status,
            visibility=visibility,
        )
    
    @rbac_guard(RESOURCE_APP, "update", resource_id_arg="app_id")
    async def update_app(self, app_id: str, data: AppUpdate) -> Optional[App]:
        """Update app.
        
        Args:
            app_id: App ID.
            data: App update data.
            
        Returns:
            Updated app or None.
        """
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
        if data.status is not None:
            app.status = data.status
        if data.visibility is not None:
            app.visibility = data.visibility
        
        return self.app_repo.update(app)
    
    @rbac_guard(RESOURCE_APP, "delete", resource_id_arg="app_id")
    async def delete_app(self, app_id: str) -> bool:
        """Delete app.
        
        Args:
            app_id: App ID.
            
        Returns:
            True if deleted.
        """
        app = self.app_repo.get_by_id(app_id)
        if not app:
            return False
        
        # Remove projections + versions + installations + market listing
        from sqlalchemy import delete

        self.db.exec(
            delete(AppComponent).where(
                and_(
                    AppComponent.app_id == app_id,
                    AppComponent.tenant_id == self.ctx.tenant_id,
                    AppComponent.workspace_id == self.ctx.workspace_id,
                )
            )
        )
        self.db.exec(
            delete(AppComponentEdge).where(
                and_(
                    AppComponentEdge.app_id == app_id,
                    AppComponentEdge.tenant_id == self.ctx.tenant_id,
                    AppComponentEdge.workspace_id == self.ctx.workspace_id,
                )
            )
        )
        self.db.exec(
            delete(AppVersionRef).where(
                and_(
                    AppVersionRef.app_id == app_id,
                    AppVersionRef.tenant_id == self.ctx.tenant_id,
                    AppVersionRef.workspace_id == self.ctx.workspace_id,
                )
            )
        )
        self.db.exec(
            delete(AppVersion).where(
                and_(
                    AppVersion.app_id == app_id,
                    AppVersion.tenant_id == self.ctx.tenant_id,
                    AppVersion.workspace_id == self.ctx.workspace_id,
                )
            )
        )
        self.db.exec(
            delete(AppMarket).where(
                and_(
                    AppMarket.app_id == app_id,
                    AppMarket.tenant_id == self.ctx.tenant_id,
                    AppMarket.workspace_id == self.ctx.workspace_id,
                )
            )
        )
        self.db.exec(
            delete(AppInstallation).where(
                and_(
                    AppInstallation.app_id == app_id,
                    AppInstallation.tenant_id == self.ctx.tenant_id,
                    AppInstallation.workspace_id == self.ctx.workspace_id,
                )
            )
        )
        self.db.commit()
        self.app_repo.delete(app_id)
        return True
    
    @rbac_guard(RESOURCE_APP, "update", resource_id_arg="app_id")
    async def create_version(self, app_id: str, data: AppVersionCreate) -> Optional[AppVersion]:
        """Create app version.
        
        Args:
            app_id: App ID.
            data: Version creation data.
            
        Returns:
            Created version or None.
        """
        app = self.app_repo.get_by_id(app_id)
        if not app:
            return None
        
        version_number = data.version
        if version_number is None:
            from sqlalchemy import select, func
            query = select(func.max(AppVersion.version)).where(
                AppVersion.app_id == app_id,
                AppVersion.tenant_id == self.ctx.tenant_id,
                AppVersion.workspace_id == self.ctx.workspace_id,
            )
            max_val = self.db.exec(query).one()
            if hasattr(max_val, "_mapping"):
                max_val = max_val[0]
            elif isinstance(max_val, (list, tuple)):
                max_val = max_val[0] if max_val else None
            version_number = int(max_val or 0) + 1

        version = AppVersion(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            app_id=app_id,
            version=version_number,
            status=data.status or "draft",
            spec_schema=data.spec_schema,
            spec_json=data.spec_json,
            changelog=data.changelog,
            created_by=self.ctx.user_id,
        )
        version = self.app_version_repo.create(version)
        
        # Update app current_version_id
        app.current_version_id = version.id
        self.app_repo.update(app)
        
        return version
    
    @rbac_guard(RESOURCE_APP, "read", resource_id_arg="app_id")
    async def list_versions(self, app_id: str) -> List[AppVersion]:
        """List app versions.
        
        Args:
            app_id: App ID.
            
        Returns:
            List of versions.
        """
        return self.app_version_repo.list_by_app(app_id)

    @rbac_guard(RESOURCE_APP, "read", resource_id_arg="app_id")
    async def list_components(self, app_id: str, version_id: str) -> List[AppComponent]:
        """List projected components for app version."""
        query = (
            select(AppComponent)
            .where(
                and_(
                    AppComponent.app_id == app_id,
                    AppComponent.app_version_id == version_id,
                    AppComponent.tenant_id == self.ctx.tenant_id,
                    AppComponent.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(AppComponent.created_at)
        )
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, AppComponent) else item[0] for item in results]

    @rbac_guard(RESOURCE_APP, "read", resource_id_arg="app_id")
    async def list_edges(self, app_id: str, version_id: str) -> List[AppComponentEdge]:
        """List projected edges for app version."""
        query = (
            select(AppComponentEdge)
            .where(
                and_(
                    AppComponentEdge.app_id == app_id,
                    AppComponentEdge.app_version_id == version_id,
                    AppComponentEdge.tenant_id == self.ctx.tenant_id,
                    AppComponentEdge.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(AppComponentEdge.created_at)
        )
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, AppComponentEdge) else item[0] for item in results]

    @rbac_guard(RESOURCE_APP, "read", resource_id_arg="app_id")
    async def list_refs(self, app_id: str, version_id: str) -> List[AppVersionRef]:
        """List external references for app version."""
        query = (
            select(AppVersionRef)
            .where(
                and_(
                    AppVersionRef.app_id == app_id,
                    AppVersionRef.app_version_id == version_id,
                    AppVersionRef.tenant_id == self.ctx.tenant_id,
                    AppVersionRef.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(AppVersionRef.created_at)
        )
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, AppVersionRef) else item[0] for item in results]

    @workspace_guard("read")
    async def impact_refs(
        self,
        ref_type: str,
        ref_id: Optional[str] = None,
        ref_key: Optional[str] = None,
    ) -> List[str]:
        """Return app_version_ids impacted by a ref."""
        if not ref_type:
            return []
        query = select(AppVersionRef.app_version_id).where(
            and_(
                AppVersionRef.tenant_id == self.ctx.tenant_id,
                AppVersionRef.workspace_id == self.ctx.workspace_id,
                AppVersionRef.ref_type == ref_type,
            )
        )
        if ref_id:
            query = query.where(AppVersionRef.ref_id == ref_id)
        if ref_key:
            query = query.where(AppVersionRef.ref_key == ref_key)
        rows = list(self.db.exec(query).all())
        out: List[str] = []
        for row in rows:
            if isinstance(row, (list, tuple)) and row:
                out.append(str(row[0]))
            elif hasattr(row, "_mapping"):
                out.append(str(row[0]))
            else:
                out.append(str(row))
        return list(dict.fromkeys(out))
    
    @rbac_guard(RESOURCE_APP, "update", resource_id_arg="app_id")
    async def publish_app(self, app_id: str, data: AppPublish) -> Optional[AppMarket]:
        """Publish app to marketplace.
        
        Args:
            app_id: App ID.
            data: Publish data.
            
        Returns:
            Market listing or None.
        """
        app = self.app_repo.get_by_id(app_id)
        if not app:
            return None
        
        version = self.app_version_repo.get_by_id(data.version_id)
        if not version or version.app_id != app_id:
            return None

        if version.status != "published":
            version.status = "published"
            self.db.commit()
            self.db.refresh(version)
        
        # Update app published_version_id
        app.published_version_id = data.version_id
        app.is_public = True
        self.app_repo.update(app)
        
        # Create or update market listing
        from sqlalchemy import select

        query = select(AppMarket).where(AppMarket.app_id == app_id)
        result = self.db.exec(query).first()
        market = result if isinstance(result, AppMarket) else result[0] if result else None
        
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

    @rbac_guard(RESOURCE_APP, "update", resource_id_arg="app_id")
    async def set_current_version(self, app_id: str, version_id: str) -> Optional[App]:
        app = self.app_repo.get_by_id(app_id)
        if not app:
            return None
        version = self.app_version_repo.get_by_id(version_id)
        if not version or version.app_id != app_id:
            raise ValidationError("Version not found")
        app.current_version_id = version_id
        app.updated_at = utc_now()
        return self.app_repo.update(app)

    @rbac_guard(RESOURCE_APP, "create", resource_id_resolver=_resolve_app_create_id)
    async def clone_app(self, source_app_id: str, data: "AppCloneRequest") -> App:
        app = self.app_repo.get_by_id(source_app_id)
        if not app:
            raise ValidationError("App not found")
        version_id = data.use_version_id or app.current_version_id
        if not version_id:
            raise ValidationError("Source app has no version to clone")
        version = self.app_version_repo.get_by_id(version_id)
        if not version or version.app_id != source_app_id:
            raise ValidationError("Version not found")

        cloned = App(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            type=app.type,
            status="active",
            visibility=data.visibility or app.visibility,
            name=data.name,
            description=data.description or app.description,
            created_by=self.ctx.user_id,
        )
        cloned = self.app_repo.create(cloned)
        new_version = AppVersion(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            app_id=cloned.id,
            version=1,
            status="draft",
            spec_schema=version.spec_schema,
            spec_json=version.spec_json,
            created_by=self.ctx.user_id,
            created_from_version_id=version.id,
            changelog="clone",
        )
        new_version = self.app_version_repo.create(new_version)
        cloned.current_version_id = new_version.id
        self.app_repo.update(cloned)
        return cloned

    @rbac_guard(RESOURCE_APP, "create", resource_id_resolver=_resolve_app_create_id)
    async def import_app(self, data: "AppImportRequest") -> App:
        app = App(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            type=(data.type or "WORKFLOW").upper(),
            status="active",
            visibility=data.visibility or "private",
            name=data.name,
            description=data.description,
            created_by=self.ctx.user_id,
        )
        app = self.app_repo.create(app)
        version = AppVersion(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            app_id=app.id,
            version=1,
            status=data.status or "draft",
            spec_schema=data.spec_schema,
            spec_json=data.spec_json,
            created_by=self.ctx.user_id,
        )
        version = self.app_version_repo.create(version)
        app.current_version_id = version.id
        self.app_repo.update(app)
        return app

    @rbac_guard(RESOURCE_APP, "read", resource_id_arg="app_id")
    async def export_version(self, app_id: str, version_id: str) -> Dict[str, Any]:
        version = self.app_version_repo.get_by_id(version_id)
        if not version or version.app_id != app_id:
            raise ValidationError("Version not found")
        return version.spec_json or {}

    @rbac_guard(RESOURCE_APP, "read", resource_id_arg="app_id")
    async def compare_versions(self, app_id: str, version_id_a: str, version_id_b: str) -> Dict[str, Any]:
        version_a = self.app_version_repo.get_by_id(version_id_a)
        version_b = self.app_version_repo.get_by_id(version_id_b)
        if not version_a or version_a.app_id != app_id:
            raise ValidationError("Version A not found")
        if not version_b or version_b.app_id != app_id:
            raise ValidationError("Version B not found")
        spec_a = version_a.spec_json or {}
        spec_b = version_b.spec_json or {}
        keys_a = set(spec_a.keys())
        keys_b = set(spec_b.keys())
        keys_added = sorted(list(keys_b - keys_a))
        keys_removed = sorted(list(keys_a - keys_b))
        keys_changed = sorted([key for key in keys_a & keys_b if spec_a.get(key) != spec_b.get(key)])
        checksum_a = checksum_json(spec_a)
        checksum_b = checksum_json(spec_b)
        return {
            "version_id_a": version_id_a,
            "version_id_b": version_id_b,
            "checksum_a": checksum_a,
            "checksum_b": checksum_b,
            "equal": checksum_a == checksum_b,
            "keys_added": keys_added,
            "keys_removed": keys_removed,
            "keys_changed": keys_changed,
        }
    
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
        return self.app_market_repo.list_public(page_size, page_token, category, featured)

    @workspace_guard("write")
    async def install_app(self, app_id: str, data: AppInstallRequest) -> AppInstallation:
        """Install an app into workspace."""
        app = self.app_repo.get_by_id(app_id)
        if not app:
            raise ValidationError("App not found")

        version_id = data.version_id or app.published_version_id or app.current_version_id
        if not version_id:
            raise ValidationError("App has no available version to install")

        existing = self.app_installation_repo.get_by_app(app_id)
        if existing:
            existing.installed_version_id = version_id
            existing.status = "active"
            existing.updated_at = utc_now()
            return self.app_installation_repo.update(existing)

        installation = AppInstallation(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            app_id=app_id,
            installed_version_id=version_id,
            status="active",
            installed_by=self.ctx.user_id,
        )
        return self.app_installation_repo.create(installation)

    @workspace_guard("read")
    async def list_installations(self) -> List[AppInstallation]:
        """List app installations for workspace."""
        return self.app_installation_repo.list_by_workspace()

    @workspace_guard("write")
    async def uninstall_app(self, installation_id: str) -> None:
        """Uninstall app from workspace."""
        self.app_installation_repo.delete(installation_id)
