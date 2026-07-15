"""Tests for the one-way MCP artifact migration."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.adapters.tools.mcp_migration import migrate_mcp_metadata
from app.api.v1.health.router import readiness_check


def test_mcp_metadata_migration_rewrites_transport_and_plaintext_bearer():
    metadata = {
        "mcp_server": {
            "name": "legacy",
            "endpoint": "https://mcp.example.com/rpc",
            "transport": "http",
            "auth_config_json": {"type": "bearer", "token": "plaintext"},
        }
    }

    migrated, secret_writes = migrate_mcp_metadata(
        metadata,
        bearer_secret_ref="secret:mcp_legacy_bearer",
        api_key_secret_ref="secret:mcp_legacy_api_key",
    )

    assert migrated["mcp_server"]["transport"] == "streamable_http"
    assert "auth_config_json" not in migrated["mcp_server"]
    assert migrated["mcp_server"]["auth_config"] == {
        "type": "bearer",
        "secret_ref": "secret:mcp_legacy_bearer",
    }
    assert secret_writes == [("secret:mcp_legacy_bearer", "plaintext")]


class _LegacyArtifactDatabase:
    def execute(self, statement):
        return None

    def exec(self, statement):
        artifact = SimpleNamespace(
            artifact_ref="mcp_server:legacy",
            metadata_json={"mcp_server": {"transport": "http"}},
        )
        return SimpleNamespace(all=lambda: [artifact])


@pytest.mark.asyncio
async def test_readiness_rejects_enabled_legacy_mcp_artifacts():
    with pytest.raises(HTTPException) as error:
        await readiness_check(db=_LegacyArtifactDatabase())

    assert error.value.status_code == 503
    assert "legacy MCP artifacts" in error.value.detail
