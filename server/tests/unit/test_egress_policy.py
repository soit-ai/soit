"""Unit tests for egress policy."""

import pytest

from app.kernel.security import egress
from app.kernel.commons.errors import ForbiddenError
from app.settings.settings import settings


def _reset_policy_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(egress, "_egress_policy", None)


def test_egress_policy_allows_configured_domain(ctx, monkeypatch):
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["*.example.com"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    _reset_policy_cache(monkeypatch)

    egress.check_egress_policy(
        ctx,
        "tool:http:test",
        {"url": "https://api.example.com/v1/health"},
    )


def test_egress_policy_denies_unlisted_domain(ctx, monkeypatch):
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["*.example.com"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    _reset_policy_cache(monkeypatch)

    with pytest.raises(ForbiddenError):
        egress.check_egress_policy(
            ctx,
            "tool:http:test",
            {"url": "https://evil.com/api"},
        )


def test_egress_policy_disabled_allows(ctx, monkeypatch):
    monkeypatch.setattr(settings, "enable_egress_policy", False)
    monkeypatch.setattr(settings, "egress_allowlist", [])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    _reset_policy_cache(monkeypatch)

    egress.check_egress_policy(
        ctx,
        "tool:http:test",
        {"url": "https://blocked.com"},
    )
