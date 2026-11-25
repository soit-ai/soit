"""Frontend boundary checks for Community edition."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WEB_APP = REPO_ROOT / "web" / "app"
WEB_ROOT = REPO_ROOT / "web"


def test_community_frontend_does_not_define_enterprise_routes_or_clients() -> None:
    routes_source = (WEB_APP / "routes.ts").read_text(encoding="utf-8")
    # The console's navigation: the rail, the context panel and the palette.
    sidebar_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((WEB_APP / "console" / "shell").glob("*.ts*"))
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
