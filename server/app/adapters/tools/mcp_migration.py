"""One-way migration helpers for official MCP SDK artifact contracts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import and_, select

from app.modules.plugin.domain.models import PluginInstalledArtifact


def mcp_metadata_issues(metadata: dict[str, Any]) -> list[str]:
    server = metadata.get("mcp_server") or {}
    issues: list[str] = []
    if server.get("transport") != "streamable_http":
        issues.append("transport")
    if not server.get("endpoint"):
        issues.append("endpoint")
    auth = server.get("auth_config") or server.get("auth_config_json") or {}
    if "token" in auth or "value" in auth:
        issues.append("plaintext_credentials")
    api_key = auth.get("api_key") or {}
    if "value" in api_key:
        issues.append("plaintext_credentials")
    if auth and auth.get("type") == "bearer" and not auth.get("secret_ref") and "token" not in auth:
        issues.append("secret_ref")
    if auth and auth.get("type") == "api_key" and not api_key.get("secret_ref") and "value" not in api_key:
        issues.append("secret_ref")
    return list(dict.fromkeys(issues))


def migrate_mcp_metadata(
    metadata: dict[str, Any],
    *,
    bearer_secret_ref: str,
    api_key_secret_ref: str,
) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    migrated = deepcopy(metadata)
    server = migrated.setdefault("mcp_server", {})
    server["transport"] = "streamable_http"
    legacy_auth = server.pop("auth_config_json", None)
    auth = deepcopy(server.get("auth_config") or legacy_auth or {})
    secret_writes: list[tuple[str, str]] = []

    if auth.get("type") == "bearer" and auth.get("token") is not None:
        secret_writes.append((bearer_secret_ref, str(auth.pop("token"))))
        auth["secret_ref"] = bearer_secret_ref
    elif auth.get("type") == "api_key":
        api_key = deepcopy(auth.get("api_key") or {})
        if api_key.get("value") is not None:
            secret_writes.append((api_key_secret_ref, str(api_key.pop("value"))))
            api_key["secret_ref"] = api_key_secret_ref
        auth["api_key"] = api_key

    server["auth_config"] = auth
    return migrated, secret_writes


def enabled_legacy_mcp_artifacts(db: Any) -> list[Any]:
    query = select(PluginInstalledArtifact).where(
        and_(
            PluginInstalledArtifact.artifact_kind == "mcp_server",
            PluginInstalledArtifact.enabled.is_(True),
            PluginInstalledArtifact.state == "enabled",
        )
    )
    legacy = []
    for raw_row in db.exec(query).all():
        artifact = (
            raw_row[0]
            if hasattr(raw_row, "__getitem__") and not isinstance(raw_row, PluginInstalledArtifact)
            else raw_row
        )
        if mcp_metadata_issues(artifact.metadata_json or {}):
            legacy.append(artifact)
    return legacy
