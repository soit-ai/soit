"""Plugin-only lifecycle and query API contract tests."""

from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi import status


def _headers() -> dict[str, str]:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


@pytest.fixture
def isolated_plugins_dir(monkeypatch, tmp_path):
    from app.settings.settings import settings

    monkeypatch.setattr(settings, "plugins_dir", str(tmp_path / "plugins"), raising=False)


def _mixed_plugin_package(
    name: str = "unified-mixed",
    version: str = "1.0.0",
    *,
    include_mcp: bool = True,
    requires_features: list[str] | None = None,
) -> bytes:
    mem = io.BytesIO()
    capabilities = ["tools", "workflow_nodes", "skills"]
    exports = {
        "tools": ["tool:http:unified_echo"],
        "workflow_nodes": ["node:tool:unified_echo"],
        "skills": ["skill:unified_triage"],
    }
    artifacts = {
        "tools": {"tool:http:unified_echo": "tools/unified_echo.json"},
        "workflow_nodes": {"node:tool:unified_echo": "nodes/unified_echo.json"},
        "skills": {"skill:unified_triage": "skills/unified_triage.json"},
    }
    if include_mcp:
        capabilities.append("mcp_servers")
        exports["mcp_servers"] = ["mcp_server:unified_mcp"]
        artifacts["mcp_servers"] = {"mcp_server:unified_mcp": "mcp/unified_mcp.json"}
    spec = {
        "name": name,
        "publisher": "soit",
        "version": version,
        "plugin_type": "mixed",
        "runtime_level": "L0",
        "capabilities": capabilities,
        "exports": exports,
        "artifacts": artifacts,
        "compatibility": {"requires_features": requires_features or []},
        "permissions": {"network": ["example.com"]},
        "integrity": {"digest": "sha256:local"},
    }
    manifest = {
        "name": name,
        "version": version,
        "runtime": {"type": "http", "base_url": "https://example.com"},
        "spec": spec,
    }
    with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("plugin.json", json.dumps(manifest))
        zf.writestr(
            "tools/unified_echo.json",
            json.dumps(
                {
                    "name": "unified_echo",
                    "adapter": "http",
                    "description": "Echo through unified plugin runtime.",
                    "input_schema": {"type": "object", "properties": {}},
                    "output_schema": {"type": "object"},
                    "http": {"url": "https://example.com/echo", "method": "POST"},
                    "policy": {"audit_level": "basic"},
                }
            ),
        )
        zf.writestr(
            "nodes/unified_echo.json",
            json.dumps(
                {
                    "name": "unified_echo",
                    "id": "node:tool:unified_echo",
                    "adapter": "tool",
                    "tool_ref": "tool:http:unified_echo",
                    "input_schema": {"type": "object", "properties": {}},
                    "output_schema": {"type": "object"},
                }
            ),
        )
        zf.writestr(
            "skills/unified_triage.json",
            json.dumps(
                {
                    "name": "unified_triage",
                    "description": "Triage requests installed from a plugin.",
                    "category": "business",
                    "visibility": "workspace",
                    "spec_json": {"instructions": "Triage urgent customer requests."},
                }
            ),
        )
        if include_mcp:
            zf.writestr(
                "mcp/unified_mcp.json",
                json.dumps(
                    {
                        "name": "unified_mcp",
                        "description": "MCP server installed from a plugin.",
                        "transport": "http",
                        "endpoint": "https://mcp.example.test",
                        "capabilities_json": {"tools": [{"name": "search", "description": "Search"}]},
                    }
                ),
            )
    return mem.getvalue()


def _create_plugin(client, *, name: str = "unified-mixed", version: str = "1.0.0") -> str:
    create_resp = client.post(
        "/api/v1/plugins",
        json={
            "name": name,
            "version": version,
            "plugin_type": "mixed",
            "spec_json": {"name": name, "publisher": "soit", "version": version, "plugin_type": "mixed"},
            "manifest_json": {"runtime": {"type": "http", "base_url": "https://example.com"}},
        },
        headers=_headers(),
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    return create_resp.json()["data"]["id"]


def _version_id_for(client, plugin_id: str, package_version: str) -> str:
    versions_resp = client.get(f"/api/v1/plugins/{plugin_id}/versions", headers=_headers())
    assert versions_resp.status_code == status.HTTP_200_OK
    versions = versions_resp.json()["data"]["items"]
    return next(item["id"] for item in versions if item["package_version"] == package_version)


def test_skill_and_mcp_public_routes_are_removed(isolated_plugins_dir, client):
    _ = isolated_plugins_dir
    removed_skill_path = "/api/v1/" + "skills"
    removed_mcp_path = "/api/v1/" + "mcp/catalog"
    assert client.get(removed_skill_path, headers=_headers()).status_code == status.HTTP_404_NOT_FOUND
    assert client.get(removed_mcp_path, headers=_headers()).status_code == status.HTTP_404_NOT_FOUND


def test_plugins_can_be_filtered_by_plugin_type(isolated_plugins_dir, client):
    _ = isolated_plugins_dir
    create_resp = client.post(
        "/api/v1/plugins",
        json={
            "name": "skill-plugin-contract",
            "version": "1.0.0",
            "plugin_type": "skill",
            "spec_json": {
                "name": "skill-plugin-contract",
                "publisher": "soit",
                "version": "1.0.0",
                "plugin_type": "skill",
                "runtime_level": "L0",
                "capabilities": ["skills"],
                "exports": {"skills": ["skill:triage"]},
                "permissions": {},
                "integrity": {"digest": "sha256:local"},
            },
            "manifest_json": {"runtime": {"type": "http", "base_url": "https://example.com"}},
        },
        headers=_headers(),
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    assert create_resp.json()["data"]["plugin_type"] == "skill"

    list_resp = client.get("/api/v1/plugins?plugin_type=skill", headers=_headers())
    assert list_resp.status_code == status.HTTP_200_OK
    items = list_resp.json()["data"]["items"]
    assert [item["name"] for item in items] == ["skill-plugin-contract"]


def test_mixed_plugin_package_projects_queryable_artifacts(isolated_plugins_dir, client):
    _ = isolated_plugins_dir
    create_resp = client.post(
        "/api/v1/plugins",
        json={
            "name": "unified-mixed",
            "version": "1.0.0",
            "plugin_type": "mixed",
            "spec_json": {"name": "unified-mixed", "publisher": "soit", "version": "1.0.0", "plugin_type": "mixed"},
            "manifest_json": {"runtime": {"type": "http", "base_url": "https://example.com"}},
        },
        headers=_headers(),
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    plugin_id = create_resp.json()["data"]["id"]

    package = _mixed_plugin_package()
    install_resp = client.post(
        f"/api/v1/plugins/{plugin_id}/install-package",
        files={"package": ("unified-mixed.zip", package, "application/zip")},
        headers=_headers(),
    )
    assert install_resp.status_code == status.HTTP_200_OK

    artifacts_resp = client.get(
        "/api/v1/plugins/artifacts?artifact_kind=mcp_server&enabled=true",
        headers=_headers(),
    )
    assert artifacts_resp.status_code == status.HTTP_200_OK
    artifacts = artifacts_resp.json()["data"]["items"]
    assert any(item["artifact_ref"] == "mcp_server:unified_mcp" for item in artifacts)

    plugin_artifacts_resp = client.get(
        f"/api/v1/plugins/{plugin_id}/artifacts",
        headers=_headers(),
    )
    assert plugin_artifacts_resp.status_code == status.HTTP_200_OK
    kinds = {item["artifact_kind"] for item in plugin_artifacts_resp.json()["data"]["items"]}
    assert kinds == {"skill", "mcp_server", "tool", "workflow_node"}

    capabilities_resp = client.get("/api/v1/plugins/capabilities?kind=mcp_tool", headers=_headers())
    assert capabilities_resp.status_code == status.HTTP_200_OK
    capability_refs = {item["ref"] for item in capabilities_resp.json()["data"]["items"]}
    assert "mcp_tool:unified_mcp:search" in capability_refs


def test_package_compatibility_uses_registered_community_features(isolated_plugins_dir, client):
    _ = isolated_plugins_dir
    create_resp = client.post(
        "/api/v1/plugins/package",
        files={
            "package": (
                "community-compatible.zip",
                _mixed_plugin_package(name="community-compatible", requires_features=["plugin.basic"]),
                "application/zip",
            )
        },
        headers=_headers(),
    )

    assert create_resp.status_code == status.HTTP_200_OK
    assert create_resp.json()["data"]["plugin"]["name"] == "community-compatible"


def test_package_compatibility_rejects_unentitled_enterprise_features(isolated_plugins_dir, client):
    _ = isolated_plugins_dir
    create_resp = client.post(
        "/api/v1/plugins/package",
        files={
            "package": (
                "enterprise-only.zip",
                _mixed_plugin_package(name="enterprise-only", requires_features=["security.sso"]),
                "application/zip",
            )
        },
        headers=_headers(),
    )

    assert create_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert create_resp.json()["message"] == "Unknown feature key: security.sso"


def test_one_click_package_upload_creates_reinstalls_upgrades_and_uninstalls(isolated_plugins_dir, client):
    _ = isolated_plugins_dir
    create_resp = client.post(
        "/api/v1/plugins/package",
        files={"package": ("unified-mixed.zip", _mixed_plugin_package(version="1.0.0"), "application/zip")},
        headers=_headers(),
    )
    assert create_resp.status_code == status.HTTP_200_OK
    create_data = create_resp.json()["data"]
    plugin = create_data["plugin"]
    plugin_id = plugin["id"]
    assert create_data["action"] == "created"
    assert plugin["name"] == "unified-mixed"
    assert plugin["version"] == "1.0.0"
    assert plugin["plugin_type"] == "mixed"
    assert plugin["publish_status"] == "published"
    assert plugin["installed"] is True
    assert plugin["enabled"] is True
    assert create_data["install"]["install_dir"]

    capabilities_resp = client.get("/api/v1/plugins/capabilities", headers=_headers())
    assert capabilities_resp.status_code == status.HTTP_200_OK
    refs = {item["ref"] for item in capabilities_resp.json()["data"]["items"]}
    assert "skill:unified_triage" in refs
    assert "mcp_tool:unified_mcp:search" in refs

    same_version_resp = client.post(
        "/api/v1/plugins/package",
        files={"package": ("unified-mixed.zip", _mixed_plugin_package(version="1.0.0"), "application/zip")},
        headers=_headers(),
    )
    assert same_version_resp.status_code == status.HTTP_409_CONFLICT
    assert same_version_resp.json()["details"]["reason"] == "same_version_exists"

    reinstall_resp = client.post(
        "/api/v1/plugins/package?mode=reinstall",
        files={"package": ("unified-mixed.zip", _mixed_plugin_package(version="1.0.0"), "application/zip")},
        headers=_headers(),
    )
    assert reinstall_resp.status_code == status.HTTP_200_OK
    reinstall_data = reinstall_resp.json()["data"]
    assert reinstall_data["action"] == "reinstalled"
    assert reinstall_data["plugin"]["id"] == plugin_id
    assert reinstall_data["plugin"]["enabled"] is True

    disable_resp = client.post(f"/api/v1/plugins/{plugin_id}/enabled", json={"enabled": False}, headers=_headers())
    assert disable_resp.status_code == status.HTTP_200_OK
    assert disable_resp.json()["data"]["state"] == "disabled"
    disabled_caps_resp = client.get("/api/v1/plugins/capabilities", headers=_headers())
    disabled_refs = {item["ref"] for item in disabled_caps_resp.json()["data"]["items"]}
    assert "skill:unified_triage" not in disabled_refs

    enable_resp = client.post(f"/api/v1/plugins/{plugin_id}/enabled", json={"enabled": True}, headers=_headers())
    assert enable_resp.status_code == status.HTTP_200_OK
    assert enable_resp.json()["data"]["state"] == "installed"
    enabled_caps_resp = client.get("/api/v1/plugins/capabilities", headers=_headers())
    enabled_refs = {item["ref"] for item in enabled_caps_resp.json()["data"]["items"]}
    assert "skill:unified_triage" in enabled_refs

    disable_again_resp = client.post(
        f"/api/v1/plugins/{plugin_id}/enabled",
        json={"enabled": False},
        headers=_headers(),
    )
    assert disable_again_resp.status_code == status.HTTP_200_OK

    upgrade_resp = client.post(
        "/api/v1/plugins/package",
        files={
            "package": (
                "unified-mixed-2.zip",
                _mixed_plugin_package(version="2.0.0", include_mcp=False),
                "application/zip",
            )
        },
        headers=_headers(),
    )
    assert upgrade_resp.status_code == status.HTTP_200_OK
    upgrade_data = upgrade_resp.json()["data"]
    assert upgrade_data["action"] == "upgraded"
    assert upgrade_data["plugin"]["id"] == plugin_id
    assert upgrade_data["plugin"]["version"] == "2.0.0"
    assert upgrade_data["plugin"]["enabled"] is True

    upgraded_artifacts_resp = client.get(f"/api/v1/plugins/{plugin_id}/artifacts", headers=_headers())
    assert upgraded_artifacts_resp.status_code == status.HTTP_200_OK
    upgraded_artifacts = upgraded_artifacts_resp.json()["data"]["items"]
    by_ref = {item["artifact_ref"]: item for item in upgraded_artifacts}
    assert by_ref["skill:unified_triage"]["enabled"] is True
    assert by_ref["mcp_server:unified_mcp"]["enabled"] is False
    assert by_ref["mcp_server:unified_mcp"]["state"] == "archived"

    uninstall_resp = client.delete(f"/api/v1/plugins/{plugin_id}/install", headers=_headers())
    assert uninstall_resp.status_code == status.HTTP_204_NO_CONTENT
    final_artifacts_resp = client.get(f"/api/v1/plugins/{plugin_id}/artifacts", headers=_headers())
    assert final_artifacts_resp.status_code == status.HTTP_200_OK
    final_artifacts = final_artifacts_resp.json()["data"]["items"]
    assert final_artifacts
    assert all(item["enabled"] is False and item["state"] == "archived" for item in final_artifacts)
    final_caps_resp = client.get("/api/v1/plugins/capabilities", headers=_headers())
    final_refs = {item["ref"] for item in final_caps_resp.json()["data"]["items"]}
    assert "skill:unified_triage" not in final_refs
    assert "mcp_tool:unified_mcp:search" not in final_refs


def test_mixed_plugin_package_uses_plugin_artifacts_without_independent_versions(isolated_plugins_dir, client):
    _ = isolated_plugins_dir
    create_resp = client.post(
        "/api/v1/plugins",
        json={
            "name": "unified-mixed",
            "version": "1.0.0",
            "plugin_type": "mixed",
            "spec_json": {"name": "unified-mixed", "publisher": "soit", "version": "1.0.0", "plugin_type": "mixed"},
            "manifest_json": {"runtime": {"type": "http", "base_url": "https://example.com"}},
        },
        headers=_headers(),
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    plugin_id = create_resp.json()["data"]["id"]

    install_resp = client.post(
        f"/api/v1/plugins/{plugin_id}/install-package",
        files={"package": ("unified-mixed.zip", _mixed_plugin_package(), "application/zip")},
        headers=_headers(),
    )
    assert install_resp.status_code == status.HTTP_200_OK

    artifacts_resp = client.get(f"/api/v1/plugins/{plugin_id}/artifacts", headers=_headers())
    assert artifacts_resp.status_code == status.HTTP_200_OK
    artifacts = artifacts_resp.json()["data"]["items"]
    skill_artifact = next(item for item in artifacts if item["artifact_kind"] == "skill")
    mcp_artifact = next(item for item in artifacts if item["artifact_kind"] == "mcp_server")
    assert skill_artifact["artifact_version_id"] is None
    assert mcp_artifact["artifact_version_id"] is None
    assert skill_artifact["plugin_version_id"] == mcp_artifact["plugin_version_id"]
    assert skill_artifact["metadata_json"]["skill"]["name"] == "unified_triage"
    assert mcp_artifact["metadata_json"]["mcp_server"]["name"] == "unified_mcp"


def test_upgrade_reconciles_removed_skill_mcp_artifacts(isolated_plugins_dir, client):
    _ = isolated_plugins_dir
    plugin_id = _create_plugin(client)

    install_resp = client.post(
        f"/api/v1/plugins/{plugin_id}/install-package",
        files={"package": ("unified-mixed.zip", _mixed_plugin_package(version="1.0.0"), "application/zip")},
        headers=_headers(),
    )
    assert install_resp.status_code == status.HTTP_200_OK

    upgrade_resp = client.post(
        f"/api/v1/plugins/{plugin_id}/upgrade-package",
        files={
            "package": (
                "unified-mixed-2.zip",
                _mixed_plugin_package(version="2.0.0", include_mcp=False),
                "application/zip",
            )
        },
        headers=_headers(),
    )
    assert upgrade_resp.status_code == status.HTTP_200_OK

    artifacts_resp = client.get(f"/api/v1/plugins/{plugin_id}/artifacts", headers=_headers())
    assert artifacts_resp.status_code == status.HTTP_200_OK
    artifacts = artifacts_resp.json()["data"]["items"]
    mcp_artifact = next(item for item in artifacts if item["artifact_ref"] == "mcp_server:unified_mcp")
    skill_artifact = next(item for item in artifacts if item["artifact_ref"] == "skill:unified_triage")
    assert mcp_artifact["enabled"] is False
    assert mcp_artifact["state"] == "archived"
    assert skill_artifact["enabled"] is True
    assert skill_artifact["plugin_version_id"] != mcp_artifact["plugin_version_id"]

    capabilities_resp = client.get("/api/v1/plugins/capabilities", headers=_headers())
    assert capabilities_resp.status_code == status.HTTP_200_OK
    refs = {item["ref"] for item in capabilities_resp.json()["data"]["items"]}
    assert "skill:unified_triage" in refs
    assert "mcp_tool:unified_mcp:search" not in refs


def test_rollback_reprojects_target_plugin_version_artifacts(isolated_plugins_dir, client):
    _ = isolated_plugins_dir
    plugin_id = _create_plugin(client)

    install_resp = client.post(
        f"/api/v1/plugins/{plugin_id}/install-package",
        files={"package": ("unified-mixed.zip", _mixed_plugin_package(version="1.0.0"), "application/zip")},
        headers=_headers(),
    )
    assert install_resp.status_code == status.HTTP_200_OK
    v1_version_id = _version_id_for(client, plugin_id, "1.0.0")

    upgrade_resp = client.post(
        f"/api/v1/plugins/{plugin_id}/upgrade-package",
        files={
            "package": (
                "unified-mixed-2.zip",
                _mixed_plugin_package(version="2.0.0", include_mcp=False),
                "application/zip",
            )
        },
        headers=_headers(),
    )
    assert upgrade_resp.status_code == status.HTTP_200_OK

    rollback_resp = client.post(
        f"/api/v1/plugins/{plugin_id}/rollback",
        json={"version_id": v1_version_id, "notes": "restore mcp capability"},
        headers=_headers(),
    )
    assert rollback_resp.status_code == status.HTTP_200_OK
    assert rollback_resp.json()["data"]["version"] == "1.0.0"

    artifacts_resp = client.get(f"/api/v1/plugins/{plugin_id}/artifacts", headers=_headers())
    assert artifacts_resp.status_code == status.HTTP_200_OK
    artifacts = artifacts_resp.json()["data"]["items"]
    mcp_artifact = next(item for item in artifacts if item["artifact_ref"] == "mcp_server:unified_mcp")
    assert mcp_artifact["enabled"] is True
    assert mcp_artifact["state"] == "enabled"
    assert mcp_artifact["plugin_version_id"] == v1_version_id

    capabilities_resp = client.get("/api/v1/plugins/capabilities?kind=mcp_tool", headers=_headers())
    assert capabilities_resp.status_code == status.HTTP_200_OK
    refs = {item["ref"] for item in capabilities_resp.json()["data"]["items"]}
    assert "mcp_tool:unified_mcp:search" in refs


def test_uninstall_disables_all_plugin_owned_capabilities(isolated_plugins_dir, client):
    _ = isolated_plugins_dir
    plugin_id = _create_plugin(client)

    install_resp = client.post(
        f"/api/v1/plugins/{plugin_id}/install-package",
        files={"package": ("unified-mixed.zip", _mixed_plugin_package(), "application/zip")},
        headers=_headers(),
    )
    assert install_resp.status_code == status.HTTP_200_OK

    uninstall_resp = client.delete(f"/api/v1/plugins/{plugin_id}/install", headers=_headers())
    assert uninstall_resp.status_code == status.HTTP_204_NO_CONTENT

    artifacts_resp = client.get(f"/api/v1/plugins/{plugin_id}/artifacts", headers=_headers())
    assert artifacts_resp.status_code == status.HTTP_200_OK
    artifacts = artifacts_resp.json()["data"]["items"]
    assert artifacts
    assert all(item["enabled"] is False and item["state"] == "archived" for item in artifacts)

    capabilities_resp = client.get("/api/v1/plugins/capabilities", headers=_headers())
    assert capabilities_resp.status_code == status.HTTP_200_OK
    refs = {item["ref"] for item in capabilities_resp.json()["data"]["items"]}
    assert "skill:unified_triage" not in refs
    assert "mcp_tool:unified_mcp:search" not in refs
