"""test_plugin_tenant_isolation

Ensure plugin installation and exported tools are isolated per tenant/workspace.
"""

import io
import json
import zipfile
from pathlib import Path

import pytest

from app.kernel.registry.deps import get_registry
from app.modules.pluginmarket.infra.installer import PluginInstaller
from app.modules.pluginmarket.runtime.loader import PluginRuntimeLoader


def _make_plugin_zip(plugin_name: str, version: str) -> bytes:
    """Create an in-memory plugin package with one exported HTTP tool."""
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("plugin.json", json.dumps({"name": plugin_name, "version": version}, ensure_ascii=False))
        z.writestr(
            "spec.json",
            json.dumps(
                {
                    "name": plugin_name,
                    "version": version,
                    "exports": {"tools": [f"tool:http:{plugin_name}:echo"]},
                    "files": {"tools": [f"{plugin_name}_echo.json"]},
                },
                ensure_ascii=False,
            ),
        )
        z.writestr(
            f"files/tools/{plugin_name}_echo.json",
            json.dumps(
                {
                    "adapter": "http",
                    "http": {"url": "https://example.com/echo", "method": "POST"},
                },
                ensure_ascii=False,
            ),
        )
    return mem.getvalue()


def test_plugin_install_isolated_by_tenant_workspace(monkeypatch, tmp_path: Path):
    # point plugins_dir to tmp
    from app.settings import settings as settings_mod
    monkeypatch.setattr(settings_mod.settings, "plugins_dir", str(tmp_path / "var_plugins"), raising=False)

    installer = PluginInstaller()
    package = _make_plugin_zip("demo", "1.0.0")

    # install same plugin into two different scopes
    r1 = installer.install_from_bytes(package, tenant_id="t1", workspace_id="w1", expected_sha256=None)
    r2 = installer.install_from_bytes(package, tenant_id="t2", workspace_id="w2", expected_sha256=None)

    assert r1.install_dir != r2.install_dir
    assert Path(r1.install_dir).exists()
    assert Path(r2.install_dir).exists()

    # load runtime and ensure tools are registered separately
    reg = get_registry()
    reg.clear_scope("t1", "w1")
    reg.clear_scope("t2", "w2")

    loader = PluginRuntimeLoader()
    loader.reload_all()  # loads all installed scopes under tmp_path

    # tool ref is derived by installer/loader; use the exported tool_ref
    tool_ref = "tool:http:demo:echo"
    assert reg.get_latest(kind="tool", tenant_id="t1", workspace_id="w1", name=tool_ref)[1] is not None
    assert reg.get_latest(kind="tool", tenant_id="t2", workspace_id="w2", name=tool_ref)[1] is not None
