"""Risk classification derived from a plugin's declared permissions.

Nothing is stored: the manifest already states what a plugin may reach, so the
classification is computed from that declaration rather than recorded beside it
where the two could disagree. A plugin that declares nothing is low risk
because it can reach nothing, not because someone marked it safe.
"""

from __future__ import annotations

from typing import Any

RISK_HIGH = "high"
RISK_MEDIUM = "medium"
RISK_LOW = "low"

_WILDCARD_HOSTS = {"*", "*.*", "0.0.0.0/0", "::/0"}


def _permissions(spec: dict[str, Any] | None, manifest: dict[str, Any] | None) -> dict[str, Any]:
    for source in (spec, manifest):
        if isinstance(source, dict):
            permissions = source.get("permissions")
            if isinstance(permissions, dict):
                return permissions
    return {}


def classify_plugin_risk(
    spec_json: dict[str, Any] | None,
    manifest_json: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    """Return the risk level and the declared scopes that produced it.

    High: the plugin can read secrets, write to storage, or reach any host.
    Medium: it can reach named hosts or read stored data.
    Low: it declares no outward reach at all.
    """
    permissions = _permissions(spec_json, manifest_json)
    reasons: list[str] = []
    level = RISK_LOW

    secrets = permissions.get("secrets")
    if isinstance(secrets, list) and secrets:
        reasons.append(f"secrets: {len(secrets)}")
        level = RISK_HIGH

    storage = permissions.get("storage")
    if isinstance(storage, dict):
        write = storage.get("write")
        read = storage.get("read")
        if isinstance(write, list) and write:
            reasons.append(f"storage write: {len(write)}")
            level = RISK_HIGH
        elif isinstance(read, list) and read:
            reasons.append(f"storage read: {len(read)}")
            if level == RISK_LOW:
                level = RISK_MEDIUM

    network = permissions.get("network")
    if isinstance(network, list) and network:
        if any(str(host).strip() in _WILDCARD_HOSTS for host in network):
            reasons.append("network: any host")
            level = RISK_HIGH
        else:
            reasons.append(f"network: {len(network)}")
            if level == RISK_LOW:
                level = RISK_MEDIUM

    return level, reasons
