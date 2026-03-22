"""test_plugin_loader

Unit tests for plugin runtime loader.
"""

import json

from app.kernel.registry.deps import get_registry
from app.modules.plugin.runtime.loader import PluginRuntimeLoader
from app.settings.settings import settings


def test_plugin_loader_registers_tools(test_context, tmp_path, monkeypatch):
    """Loader registers tools from installed plugin fixtures."""
    reg = get_registry()
    reg.clear_scope(tenant_id=test_context.tenant_id, workspace_id=test_context.workspace_id)

    plugins_root = tmp_path / "plugins"
    install_dir = (
        plugins_root
        / "installed"
        / test_context.tenant_id
        / test_context.workspace_id
        / "soit-plugin-health"
        / "0.1.0"
    )
    tools_dir = install_dir / "files" / "tools"
    nodes_dir = install_dir / "files" / "nodes"
    tools_dir.mkdir(parents=True, exist_ok=True)
    nodes_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "name": "soit-plugin-health",
        "version": "0.1.0",
        "enabled": True,
        "runtime": {
            "type": "http",
            "base_url": "http://plugin-runtime:8000",
        },
    }
    spec = {
        "name": "soit-plugin-health",
        "publisher": "soit",
        "version": "0.1.0",
        "description": "Health check tools for local testing.",
        "runtime_level": "L0",
        "capabilities": ["tools", "workflow_nodes"],
        "exports": {
            "tools": ["tool:http:health_check"],
            "workflow_nodes": ["node:tool:health_check"],
        },
        "permissions": {
            "network": ["plugin-runtime"],
        },
        "integrity": {"digest": "sha256:dev"},
    }
    tool_spec = {
        "name": "health_check",
        "id": "tool:http:health_check",
        "adapter": "http",
        "description": "Call health endpoint.",
        "input_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object"},
        "http": {"method": "GET", "url": "http://plugin-runtime:8000/health"},
        "policy": {"audit_level": "basic"},
    }
    node_spec = {
        "name": "health_check",
        "id": "node:tool:health_check",
        "adapter": "tool",
        "tool_ref": "tool:http:health_check",
        "input_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object"},
    }

    (install_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (install_dir / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    (tools_dir / "health_check.json").write_text(json.dumps(tool_spec), encoding="utf-8")
    (nodes_dir / "health_check.json").write_text(json.dumps(node_spec), encoding="utf-8")

    monkeypatch.setattr(settings, "plugins_dir", str(plugins_root))

    loader = PluginRuntimeLoader()
    loaded = loader.load_all()
    assert any(p.name == "soit-plugin-health" for p in loaded)

    tool = reg.get_latest(
        kind="tool",
        tenant_id=test_context.tenant_id,
        workspace_id=test_context.workspace_id,
        name="tool:http:health_check",
    )
    assert tool is not None

    node = reg.get_latest(
        kind="workflow_node",
        tenant_id=test_context.tenant_id,
        workspace_id=test_context.workspace_id,
        name="node:tool:health_check",
    )
    assert node is not None


def test_plugin_loader_blocks_localhost_runtime(test_context, tmp_path, monkeypatch):
    """Loader skips plugins that point to localhost runtime when not allowed."""
    reg = get_registry()
    reg.clear_scope(tenant_id=test_context.tenant_id, workspace_id=test_context.workspace_id)

    plugins_root = tmp_path / "plugins"
    install_dir = (
        plugins_root
        / "installed"
        / test_context.tenant_id
        / test_context.workspace_id
        / "soit-plugin-local"
        / "0.1.0"
    )
    tools_dir = install_dir / "files" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "name": "soit-plugin-local",
        "version": "0.1.0",
        "enabled": True,
        "runtime": {
            "type": "http",
            "base_url": "http://localhost:8000",
        },
    }
    spec = {
        "name": "soit-plugin-local",
        "publisher": "soit",
        "version": "0.1.0",
        "description": "Local runtime plugin.",
        "runtime_level": "L0",
        "capabilities": ["tools"],
        "exports": {"tools": ["tool:http:local_check"]},
        "permissions": {
            "network": ["localhost"],
        },
        "integrity": {"digest": "sha256:dev"},
    }
    tool_spec = {
        "name": "local_check",
        "id": "tool:http:local_check",
        "adapter": "http",
        "description": "Call local endpoint.",
        "input_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object"},
        "http": {"method": "GET", "url": "http://localhost:8000/health"},
        "policy": {"audit_level": "basic"},
    }

    (install_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (install_dir / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    (tools_dir / "local_check.json").write_text(json.dumps(tool_spec), encoding="utf-8")

    monkeypatch.setattr(settings, "plugins_dir", str(plugins_root))
    monkeypatch.setattr(settings, "plugin_runtime_allow_localhost", False)

    loader = PluginRuntimeLoader()
    loaded = loader.load_all()
    assert loaded == []

    tool = reg.get_latest(
        kind="tool",
        tenant_id=test_context.tenant_id,
        workspace_id=test_context.workspace_id,
        name="tool:http:local_check",
    )
    assert tool is None
