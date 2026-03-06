""" handlers

AppCenter handlers (thin orchestration).
"""

from typing import Optional

from app.kernel.contracts.context import RequestContext
from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.modules.appcenter.application.service import AppService
from app.modules.appcenter.application.schemas import (
    AppCreate,
    AppUpdate,
    AppVersionCreate,
    AppPublish,
    AppCloneRequest,
    AppImportRequest,
    AppResponse,
    AppVersionResponse,
    AppMarketResponse,
    AppInstallRequest,
    AppInstallationResponse,
    AppComponentResponse,
    AppComponentEdgeResponse,
    AppVersionRefResponse,
    RefImpactResponse,
    AppExportResponse,
    AppVersionCompareRequest,
    AppVersionCompareResponse,
)


class AppCenterHandlers:
    """Handlers for AppCenter API endpoints."""

    def __init__(self, service: AppService):
        self.service = service

    async def create_app(self, ctx: RequestContext, app_in: AppCreate) -> AppResponse:
        """Create an app."""
        app = await self.service.create_app(app_in)
        return AppResponse.model_validate(app)

    async def list_apps(
        self,
        ctx: RequestContext,
        page_token: Optional[str] = None,
        page_size: int = 20,
        search: Optional[str] = None,
        app_type: Optional[str] = None,
        status: Optional[str] = None,
        visibility: Optional[str] = None,
    ) -> PaginatedResponse[AppResponse]:
        """List apps."""
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        apps = await self.service.list_apps(
            page_size=limit + 1,
            page_token=None,
            search=search,
            app_type=app_type,
            status=status,
            visibility=visibility,
        )

        items = apps.items[:limit]
        has_next = len(apps.items) > limit
        next_offset = offset + len(items) if has_next else None

        return PaginatedResponse.create(
            items=[AppResponse.model_validate(item) for item in items],
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )

    async def get_app(self, ctx: RequestContext, app_id: str) -> AppResponse:
        """Get app by id."""
        app = await self.service.get_app(app_id)
        return AppResponse.model_validate(app)

    async def update_app(self, ctx: RequestContext, app_id: str, app_in: AppUpdate) -> AppResponse:
        """Update app."""
        app = await self.service.update_app(app_id, app_in)
        return AppResponse.model_validate(app)

    async def delete_app(self, ctx: RequestContext, app_id: str) -> None:
        """Delete app."""
        await self.service.delete_app(app_id)

    async def create_version(
        self,
        ctx: RequestContext,
        app_id: str,
        version_in: AppVersionCreate,
    ) -> AppVersionResponse:
        """Create app version."""
        version = await self.service.create_version(app_id, version_in)
        return AppVersionResponse.model_validate(version)

    async def set_current_version(self, ctx: RequestContext, app_id: str, version_id: str) -> AppResponse:
        app = await self.service.set_current_version(app_id, version_id)
        return AppResponse.model_validate(app)

    async def list_versions(self, ctx: RequestContext, app_id: str) -> list[AppVersionResponse]:
        """List app versions."""
        versions = await self.service.list_versions(app_id)
        return [AppVersionResponse.model_validate(item) for item in versions]

    async def publish_app(
        self,
        ctx: RequestContext,
        app_id: str,
        publish_in: AppPublish,
    ) -> AppMarketResponse:
        """Publish app to marketplace."""
        market = await self.service.publish_app(app_id, publish_in)
        return AppMarketResponse.model_validate(market)

    async def clone_app(self, ctx: RequestContext, app_id: str, data: AppCloneRequest) -> AppResponse:
        cloned = await self.service.clone_app(app_id, data)
        return AppResponse.model_validate(cloned)

    async def import_app(self, ctx: RequestContext, data: AppImportRequest) -> AppResponse:
        app = await self.service.import_app(data)
        return AppResponse.model_validate(app)

    async def list_marketplace(
        self,
        ctx: RequestContext,
        page_token: Optional[str] = None,
        page_size: int = 20,
        category: Optional[str] = None,
        featured: Optional[bool] = None,
    ) -> PaginatedResponse[AppMarketResponse]:
        """List marketplace apps."""
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        listings = self.service.list_marketplace(
            page_size=limit + 1,
            page_token=None,
            category=category,
            featured=featured,
        )

        items = listings.items[:limit]
        has_next = len(listings.items) > limit
        next_offset = offset + len(items) if has_next else None

        return PaginatedResponse.create(
            items=[AppMarketResponse.model_validate(item) for item in items],
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )

    async def install_app(
        self,
        ctx: RequestContext,
        app_id: str,
        install_in: AppInstallRequest,
    ) -> AppInstallationResponse:
        """Install app into workspace."""
        installation = await self.service.install_app(app_id, install_in)
        return AppInstallationResponse.model_validate(installation)

    async def list_installations(
        self,
        ctx: RequestContext,
    ) -> list[AppInstallationResponse]:
        """List app installations."""
        items = await self.service.list_installations()
        return [AppInstallationResponse.model_validate(item) for item in items]

    async def uninstall_app(
        self,
        ctx: RequestContext,
        installation_id: str,
    ) -> None:
        """Uninstall app from workspace."""
        await self.service.uninstall_app(installation_id)

    async def list_components(
        self,
        ctx: RequestContext,
        app_id: str,
        version_id: str,
    ) -> list[AppComponentResponse]:
        """List components for app version."""
        items = await self.service.list_components(app_id, version_id)
        return [AppComponentResponse.model_validate(item) for item in items]

    async def list_edges(
        self,
        ctx: RequestContext,
        app_id: str,
        version_id: str,
    ) -> list[AppComponentEdgeResponse]:
        """List edges for app version."""
        items = await self.service.list_edges(app_id, version_id)
        return [AppComponentEdgeResponse.model_validate(item) for item in items]

    async def list_refs(
        self,
        ctx: RequestContext,
        app_id: str,
        version_id: str,
    ) -> list[AppVersionRefResponse]:
        """List refs for app version."""
        items = await self.service.list_refs(app_id, version_id)
        return [AppVersionRefResponse.model_validate(item) for item in items]

    async def export_version(
        self,
        ctx: RequestContext,
        app_id: str,
        version_id: str,
        *,
        format: str = "json",
    ) -> AppExportResponse:
        spec = await self.service.export_version(app_id, version_id)
        normalized = (format or "json").lower()
        if normalized == "yaml":
            import yaml
            payload = yaml.safe_dump(spec, sort_keys=False)
        else:
            payload = spec
            normalized = "json"
        return AppExportResponse(format=normalized, spec=payload)

    async def compare_versions(
        self,
        ctx: RequestContext,
        app_id: str,
        data: AppVersionCompareRequest,
    ) -> AppVersionCompareResponse:
        result = await self.service.compare_versions(
            app_id,
            data.version_id_a,
            data.version_id_b,
        )
        return AppVersionCompareResponse(**result)

    async def impact_refs(
        self,
        ctx: RequestContext,
        ref_type: str,
        ref_id: Optional[str] = None,
        ref_key: Optional[str] = None,
    ) -> RefImpactResponse:
        """List app versions impacted by a ref."""
        version_ids = await self.service.impact_refs(ref_type=ref_type, ref_id=ref_id, ref_key=ref_key)
        return RefImpactResponse(
            ref_type=ref_type,
            ref_id=ref_id,
            ref_key=ref_key,
            app_version_ids=version_ids,
        )
