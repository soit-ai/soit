"""Frontend boundary checks for Community edition."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WEB_APP = REPO_ROOT / "web" / "app"
WEB_ROOT = REPO_ROOT / "web"


def test_community_frontend_does_not_define_enterprise_routes_or_clients() -> None:
    routes_source = (WEB_APP / "routes.ts").read_text(encoding="utf-8")
    sidebar_source = (WEB_APP / "components" / "nav" / "root-sidebar.tsx").read_text(
        encoding="utf-8"
    )

    assert "prefix('/enterprise'" not in routes_source
    assert 'prefix("/enterprise"' not in routes_source
    assert "/enterprise/governance" not in routes_source
    assert "/enterprise/governance" not in sidebar_source
    assert "type: 'enterprise'" not in sidebar_source
    assert "title: 'Enterprise'" not in sidebar_source
    assert not (WEB_APP / "routes" / "enterprise").exists()
    assert not (WEB_APP / "services" / "enterprise-governance-service.ts").exists()
    assert not (WEB_ROOT / "e2e" / "enterprise-governance.spec.ts").exists()
