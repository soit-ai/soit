"""Release identity and Community manifest truth contracts."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
RELEASE_VERSION = "1.0.0"


def _env_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def test_release_version_is_consistent_across_public_manifests() -> None:
    server_package = tomllib.loads((ROOT / "server" / "pyproject.toml").read_text(encoding="utf-8"))
    web_package = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))
    root_env = _env_values(ROOT / ".env.example")
    server_env = _env_values(ROOT / "server" / ".env.example")

    assert server_package["project"]["version"] == RELEASE_VERSION
    assert web_package["version"] == RELEASE_VERSION
    assert root_env["PLATFORM_VERSION"] == RELEASE_VERSION
    assert server_env["PLATFORM_VERSION"] == RELEASE_VERSION

    main_source = (ROOT / "server" / "app" / "main.py").read_text(encoding="utf-8")
    assert "version=app_settings.platform_version" in main_source
    assert 'version="1.0.0"' not in main_source


def test_community_environment_examples_use_current_entitlement_keys() -> None:
    root_env = _env_values(ROOT / ".env.example")
    server_env = _env_values(ROOT / "server" / ".env.example")

    for values in (root_env, server_env):
        assert values["PLATFORM_EDITION"] == "community"
        assert values["PLATFORM_ENTITLEMENTS"] == "[]"
        assert values["ENABLE_EGRESS_POLICY"] == "true"
        assert values["EGRESS_ALLOWLIST"] == "[]"
        assert values["EGRESS_BLOCKLIST"] == "[]"
        assert "PLATFORM_FEATURES" not in values


def test_compose_passes_the_public_runtime_manifest_to_every_backend_process() -> None:
    compose = yaml.safe_load((ROOT / "docker" / "docker-compose.yml").read_text(encoding="utf-8"))
    environment = compose["services"]["migrate"]["environment"]

    assert environment["PLATFORM_VERSION"] == "${PLATFORM_VERSION:-1.0.0}"
    assert environment["PLATFORM_EDITION"] == "${PLATFORM_EDITION:-community}"
    assert environment["PLATFORM_ENTITLEMENTS"] == "${PLATFORM_ENTITLEMENTS:-[]}"
    assert environment["ENABLE_EGRESS_POLICY"] == "${ENABLE_EGRESS_POLICY:-true}"
    assert environment["EGRESS_ALLOWLIST"] == "${EGRESS_ALLOWLIST:-[]}"
    assert environment["EGRESS_BLOCKLIST"] == "${EGRESS_BLOCKLIST:-[]}"

    required_keys = {
        "PLATFORM_VERSION",
        "PLATFORM_EDITION",
        "PLATFORM_ENTITLEMENTS",
        "ENABLE_EGRESS_POLICY",
        "EGRESS_ALLOWLIST",
        "EGRESS_BLOCKLIST",
    }
    for service_name in ("migrate", "bootstrap", "api", "knowledge-ingest-worker", "outbox-dispatcher"):
        service_environment = compose["services"][service_name]["environment"]
        assert {key: service_environment[key] for key in required_keys} == {
            key: environment[key] for key in required_keys
        }


def test_public_readmes_describe_the_community_runtime_without_stale_services() -> None:
    english = (ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (ROOT / "README-cn.md").read_text(encoding="utf-8")

    assert "SOIT Community" in english
    assert "at-least-once" in english
    assert "no side effect is duplicated" not in english
    assert "pre-loaded" not in english

    for stale_claim in (
        "aiohttp 3.11+",
        "openai 1.6.1",
        "TypeScript 5.8",
        "Vite 6",
        "Nginx (",
        "Celery Worker",
        "Flower (",
        "mypy 1.15+",
    ):
        assert stale_claim not in chinese

    assert "server/app/" in chinese
    assert "outbox-dispatcher" in chinese


def test_community_source_has_no_private_runtime_package_dependency() -> None:
    dependency_files = [
        ROOT / "server" / "pyproject.toml",
        ROOT / "server" / "uv.lock",
        ROOT / "web" / "package.json",
        ROOT / "web" / "package-lock.json",
    ]
    for path in dependency_files:
        content = path.read_text(encoding="utf-8").lower()
        assert "soit-enterprise" not in content
        assert "soit_enterprise" not in content


def test_product_navigation_has_no_hash_only_links() -> None:
    for path in (ROOT / "web" / "app").rglob("*.tsx"):
        assert 'href="#"' not in path.read_text(encoding="utf-8"), path

    sidebar_source = (ROOT / "web" / "app" / "components" / "nav" / "root-sidebar.tsx").read_text(
        encoding="utf-8"
    )
    team_switcher_source = (
        ROOT / "web" / "app" / "components" / "common" / "team-switcher.tsx"
    ).read_text(encoding="utf-8")
    for fake_team_label in ("Acme Inc", "Acme Corp.", "Evil Corp.", "Add team"):
        assert fake_team_label not in sidebar_source
        assert fake_team_label not in team_switcher_source


def test_runtime_source_does_not_claim_unimplemented_production_guardrails() -> None:
    for path in (ROOT / "server" / "app").rglob("*.py"):
        assert "Placeholder: In production" not in path.read_text(encoding="utf-8"), path
