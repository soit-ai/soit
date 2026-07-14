"""Feature registry and entitlement resolution tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.kernel.entitlements.features import FeatureRegistry, resolve_enabled_features


def test_feature_registry_loads_default_community_feature_keys() -> None:
    registry = FeatureRegistry.default()

    assert registry.get("agent.runtime").kind == "product"
    assert registry.get("plugin.basic").editions == frozenset({"community", "enterprise", "cloud"})
    with pytest.raises(ValueError, match="Unknown feature key"):
        registry.get("security.sso")
    with pytest.raises(ValueError, match="Unknown feature key"):
        registry.get("cloud.billing")


def test_community_entitlements_enable_only_community_features_by_default() -> None:
    enabled = resolve_enabled_features(edition="community")

    assert "agent.runtime" in enabled
    assert "workflow.runtime" in enabled
    assert "plugin.basic" in enabled
    assert "security.sso" not in enabled
    assert "deployment.offline_license" not in enabled


def test_enterprise_entitlements_are_limited_to_registered_enterprise_features(tmp_path: Path) -> None:
    registry = FeatureRegistry.default(
        extra_files=[
            _feature_file(
                tmp_path,
                "enterprise-features.json",
                {
                    "owner": "enterprise-test",
                    "features": [
                        {
                            "key": "security.sso",
                            "editions": ["enterprise", "cloud"],
                            "kind": "product",
                        },
                        {
                            "key": "security.scim",
                            "editions": ["enterprise", "cloud"],
                            "kind": "product",
                        },
                        {
                            "key": "cloud.billing",
                            "editions": ["cloud"],
                            "kind": "saas_ops",
                        },
                    ],
                },
            )
        ]
    )
    enabled = resolve_enabled_features(
        edition="enterprise",
        entitlement_keys=["security.sso", "security.scim", "cloud.billing"],
        registry=registry,
    )

    assert "security.sso" in enabled
    assert "security.scim" in enabled
    assert "cloud.billing" not in enabled


def test_feature_registry_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    feature_file = _feature_file(
        tmp_path,
        "duplicate-features.json",
        {
            "owner": "duplicate-test",
            "features": [
                {"key": "agent.runtime", "editions": ["community"], "kind": "product"},
            ],
        }
    )

    with pytest.raises(ValueError, match="Duplicate feature key"):
        FeatureRegistry.default(extra_files=[feature_file])


def test_feature_registry_rejects_invalid_json_shape(tmp_path: Path) -> None:
    feature_file = _feature_file(
        tmp_path,
        "invalid-features.json",
        {
            "version": 2,
            "owner": "bad-test",
            "features": [
                {"key": "bad.feature", "editions": ["community"], "kind": "product"},
            ],
        }
    )

    with pytest.raises(ValueError, match="version"):
        FeatureRegistry.from_json_file(feature_file)


def test_unknown_entitlement_keys_are_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown feature key"):
        resolve_enabled_features(edition="enterprise", entitlement_keys=["security.unknown"])


def _feature_file(tmp_path: Path, name: str, payload: dict) -> str:
    data = {"version": 1, **payload}
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)
