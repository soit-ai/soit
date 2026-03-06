"""test_pluginmarket_handlers

Validate plugin handler responses include installation state.
"""

import pytest

from app.modules.pluginmarket.domain.models import Plugin, PluginInstallation
from app.modules.pluginmarket.infra.repository import PluginRepository, PluginInstallationRepository
from app.modules.pluginmarket.infra.installer import PluginInstaller
from app.modules.pluginmarket.application.service import PluginMarketService
from app.api.v1.pluginmarket.handlers import PluginMarketHandlers


def _build_service(db, ctx) -> PluginMarketService:
    plugin_repo = PluginRepository(db, ctx)
    installation_repo = PluginInstallationRepository(db, ctx)
    installer = PluginInstaller()
    return PluginMarketService(db, ctx, plugin_repo, installation_repo, installer)


@pytest.mark.asyncio
async def test_list_plugins_includes_installation_state(db, ctx):
    service = _build_service(db, ctx)
    plugin_repo = PluginRepository(db, ctx)
    installation_repo = PluginInstallationRepository(db, ctx)

    plugin = Plugin(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="demo",
        version="1.0.0",
        description="demo plugin",
        spec_json={"name": "demo"},
        manifest_json={"runtime": {"type": "http", "base_url": "https://example.com"}},
        metadata_json=None,
        published=True,
        installed_count=0,
        created_by=ctx.user_id,
    )
    plugin = plugin_repo.create(plugin)

    handlers = PluginMarketHandlers(service)
    response = await handlers.list_plugins(ctx, published_only=False, page_token=None, page_size=20)

    assert len(response.items) == 1
    assert response.items[0].installed is False
    assert response.items[0].enabled is None

    installation = PluginInstallation(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        plugin_id=plugin.id,
        installed_by=ctx.user_id,
        config_json={"enabled": False},
    )
    installation_repo.create(installation)

    response = await handlers.list_plugins(ctx, published_only=False, page_token=None, page_size=20)
    assert response.items[0].installed is True
    assert response.items[0].enabled is False


@pytest.mark.asyncio
async def test_get_plugin_includes_installation_state(db, ctx):
    service = _build_service(db, ctx)
    plugin_repo = PluginRepository(db, ctx)
    installation_repo = PluginInstallationRepository(db, ctx)

    plugin = Plugin(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="demo",
        version="1.1.0",
        description=None,
        spec_json={"name": "demo"},
        manifest_json={"runtime": {"type": "http", "base_url": "https://example.com"}},
        metadata_json=None,
        published=False,
        installed_count=0,
        created_by=ctx.user_id,
    )
    plugin = plugin_repo.create(plugin)

    installation = PluginInstallation(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        plugin_id=plugin.id,
        installed_by=ctx.user_id,
        config_json={"enabled": True},
    )
    installation_repo.create(installation)

    handlers = PluginMarketHandlers(service)
    response = await handlers.get_plugin(ctx, plugin.id)

    assert response.installed is True
    assert response.enabled is True
