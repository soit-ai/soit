"""test_appcenter_service

Unit tests for AppCenter service.
"""

from app.modules.appcenter.application.service import AppService
from app.modules.appcenter.application.schemas import (
    AppCreate,
    AppUpdate,
    AppVersionCreate,
    AppPublish,
)
from app.modules.appcenter.infra.repository import (
    AppRepository,
    AppVersionRepository,
    AppMarketRepository,
    AppInstallationRepository,
)


def _build_service(db, ctx) -> AppService:
    return AppService(
        db=db,
        ctx=ctx,
        app_repo=AppRepository(db, ctx),
        app_version_repo=AppVersionRepository(db, ctx),
        app_market_repo=AppMarketRepository(db, ctx),
        app_installation_repo=AppInstallationRepository(db, ctx),
    )


import pytest


@pytest.mark.asyncio
async def test_appcenter_create_update_delete(db, tenant1_ctx):
    """Create/update/delete app works."""
    service = _build_service(db, tenant1_ctx)
    app = await service.create_app(AppCreate(name="app-1", description="demo"))
    assert app.id
    assert app.name == "app-1"

    updated = await service.update_app(app.id, AppUpdate(description="updated"))
    assert updated.description == "updated"

    deleted = await service.delete_app(app.id)
    assert deleted is True


@pytest.mark.asyncio
async def test_appcenter_version_and_publish(db, tenant1_ctx):
    """Create version and publish to marketplace."""
    service = _build_service(db, tenant1_ctx)
    app = await service.create_app(AppCreate(name="app-2", description="demo"))

    version = await service.create_version(
        app.id,
        AppVersionCreate(
            spec_schema="workflow.v1",
            spec_json={
                "name": "app-2",
                "inputs_schema": {},
                "outputs_schema": {},
                "graph": {
                    "nodes": [{"id": "n1", "type": "output", "params": {"value": "ok"}}],
                    "edges": [],
                },
            },
            changelog="init",
        ),
    )
    assert version.id

    versions = await service.list_versions(app.id)
    assert len(versions) == 1
    assert versions[0].id == version.id

    market = await service.publish_app(app.id, AppPublish(version_id=version.id, featured=True))
    assert market is not None
    assert market.app_id == app.id
    assert market.published_version_id == version.id

    listings = service.list_marketplace(page_size=20, page_token=None, category=None, featured=True)
    assert any(item.app_id == app.id for item in listings.items)
