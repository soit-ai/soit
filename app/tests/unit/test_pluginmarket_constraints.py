"""test_pluginmarket_constraints

Validate plugin conflict detection and upgrade compatibility guards.
"""

import io
import json
import zipfile
from pathlib import Path

import pytest

from app.kernel.commons.errors import ValidationError
from app.kernel.registry.deps import get_registry
from app.modules.appcenter.domain.models import App, AppVersion, AppMarket
from app.modules.pluginmarket.domain.models import Plugin
from app.modules.pluginmarket.infra.installer import PluginInstaller
from app.modules.pluginmarket.infra.repository import PluginRepository, PluginInstallationRepository
from app.modules.pluginmarket.application.service import PluginMarketService


def _make_plugin_zip(plugin_name: str, version: str, tool_name: str) -> bytes:
    tool_ref = f"tool:http:{tool_name}"
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "plugin.json",
            json.dumps(
                {
                    "name": plugin_name,
                    "version": version,
                    "runtime": {"type": "http", "base_url": "https://example.com"},
                },
                ensure_ascii=False,
            ),
        )
        z.writestr(
            "spec.json",
            json.dumps(
                {
                    "name": plugin_name,
                    "publisher": "soit",
                    "version": version,
                    "runtime_level": "L0",
                    "capabilities": ["tools"],
                    "exports": {"tools": [tool_ref]},
                    "permissions": {"network": ["example.com"]},
                    "integrity": {"digest": "sha256:local"},
                },
                ensure_ascii=False,
            ),
        )
        z.writestr(
            f"tools/{tool_name}.json",
            json.dumps(
                {
                    "name": tool_name,
                    "adapter": "http",
                    "input_schema": {"type": "object", "properties": {}},
                    "output_schema": {"type": "object", "properties": {}},
                    "http": {"url": "https://example.com/echo", "method": "POST"},
                    "policy": {"audit_level": "basic"},
                },
                ensure_ascii=False,
            ),
        )
    return mem.getvalue()


def _build_service(db, ctx, tmp_path: Path, monkeypatch) -> PluginMarketService:
    from app.settings import settings as settings_mod

    monkeypatch.setattr(
        settings_mod.settings,
        "plugins_dir",
        str(tmp_path / "var_plugins"),
        raising=False,
    )
    plugin_repo = PluginRepository(db, ctx)
    installation_repo = PluginInstallationRepository(db, ctx)
    installer = PluginInstaller()
    return PluginMarketService(db, ctx, plugin_repo, installation_repo, installer)


@pytest.mark.asyncio
async def test_plugin_install_blocks_conflicting_exports(db, ctx, tmp_path: Path, monkeypatch):
    service = _build_service(db, ctx, tmp_path, monkeypatch)
    plugin_repo = PluginRepository(db, ctx)

    plugin = Plugin(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="demo",
        version="1.0.0",
        description="demo",
        spec_json={},
        manifest_json={},
        metadata_json=None,
        published=False,
        installed_count=0,
        created_by=ctx.user_id,
    )
    plugin = plugin_repo.create(plugin)

    package_v1 = _make_plugin_zip("demo", "1.0.0", "demo_tool")
    await service.install_plugin_package(plugin.id, package_v1)

    reg = get_registry()
    reg.register(
        kind="tool",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="tool:http:conflict_tool",
        version="1.0.0",
        payload={
            "tool_spec": {
                "name": "conflict_tool",
                "adapter": "http",
                "input_schema": {"type": "object", "properties": {}},
                "output_schema": {"type": "object", "properties": {}},
                "http": {"url": "https://example.com", "method": "POST"},
                "policy": {"audit_level": "basic"},
            },
            "plugin": {"name": "other", "version": "1.0.0"},
        },
    )

    package = _make_plugin_zip("demo", "1.0.0", "conflict_tool")

    with pytest.raises(ValidationError):
        await service.install_plugin_package(plugin.id, package)


@pytest.mark.asyncio
async def test_plugin_upgrade_blocks_breaking_published_workflows(db, ctx, tmp_path: Path, monkeypatch):
    service = _build_service(db, ctx, tmp_path, monkeypatch)
    plugin_repo = PluginRepository(db, ctx)

    current_spec = {
        "name": "demo",
        "publisher": "soit",
        "version": "1.0.0",
        "runtime_level": "L0",
        "capabilities": ["tools"],
        "exports": {"tools": ["tool:http:demo_tool"]},
        "permissions": {"network": ["example.com"]},
        "integrity": {"digest": "sha256:local"},
    }
    plugin = Plugin(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="demo",
        version="1.0.0",
        description="demo",
        spec_json=current_spec,
        manifest_json={"runtime": {"type": "http", "base_url": "https://example.com"}},
        metadata_json=None,
        published=False,
        installed_count=0,
        created_by=ctx.user_id,
    )
    plugin = plugin_repo.create(plugin)

    app_version = AppVersion(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        app_id="app_demo",
        version=1,
        status="published",
        spec_schema="workflow.v1",
        spec_json={
            "name": "demo-workflow",
            "inputs_schema": {},
            "outputs_schema": {},
            "graph": {
                "nodes": [
                    {
                        "id": "tool1",
                        "type": "tool",
                        "params": {"tool_ref": "tool:http:demo_tool"},
                    }
                ],
                "edges": [],
            },
        },
        created_by=ctx.user_id,
    )
    db.add(app_version)
    db.commit()

    app = App(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        type="WORKFLOW",
        status="active",
        visibility="private",
        name="demo-app",
        description="demo",
        current_version_id=app_version.id,
        published_version_id=app_version.id,
        is_public=True,
        created_by=ctx.user_id,
    )
    db.add(app)
    db.commit()
    market = AppMarket(
        app_id=app.id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        published_version_id=app_version.id,
        featured=False,
    )
    db.add(market)
    db.commit()

    package = _make_plugin_zip("demo", "2.0.0", "new_tool")

    with pytest.raises(ValidationError):
        await service.upgrade_plugin_package(plugin.id, package)
