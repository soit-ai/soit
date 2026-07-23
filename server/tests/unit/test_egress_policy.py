"""Unit tests for egress policy."""

import pytest

from app.kernel.commons.errors import ForbiddenError
from app.kernel.contracts.context import RequestContext
from app.kernel.security import egress
from app.settings.settings import settings


def _reset_policy_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(egress, "_egress_policy", None)


def _disable_db_policy_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.infra.db.session as db_session

    monkeypatch.setattr(
        db_session,
        "get_db_sync",
        lambda: (_ for _ in ()).throw(RuntimeError("DB disabled in unit test")),
    )


class AllowApiExampleProvider:
    def get_scope_policy(self, ctx):
        return egress.EgressScopePolicy(
            tenant_allowlist=["api.example.com"],
            tenant_blocklist=[],
            workspace_allowlist=[],
            workspace_blocklist=[],
        )


class FailingScopePolicyProvider:
    def get_scope_policy(self, ctx):
        raise RuntimeError("policy lookup failed")


class StaticAddressResolver:
    def __init__(self, addresses: list[str]) -> None:
        self.addresses = addresses

    async def resolve(self, hostname: str, port: int) -> list[str]:
        return self.addresses


class RecordingAddressResolver(StaticAddressResolver):
    def __init__(self, addresses: list[str]) -> None:
        super().__init__(addresses)
        self.calls: list[tuple[str, int]] = []

    async def resolve(self, hostname: str, port: int) -> list[str]:
        self.calls.append((hostname, port))
        return await super().resolve(hostname, port)


def test_egress_policy_allows_configured_domain(ctx, monkeypatch):
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["*.example.com"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    _reset_policy_cache(monkeypatch)
    _disable_db_policy_lookup(monkeypatch)

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
    _disable_db_policy_lookup(monkeypatch)

    with pytest.raises(ForbiddenError):
        egress.check_egress_policy(
            ctx,
            "tool:http:test",
            {"url": "https://evil.com/api"},
        )


def test_egress_denial_details_do_not_expose_url_credentials(ctx, monkeypatch):
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["allowed.example.com"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    _reset_policy_cache(monkeypatch)

    with pytest.raises(ForbiddenError) as exc_info:
        egress.check_egress_policy(
            ctx,
            "model-provider:test",
            {"url": "https://evil.example.com/webhook/token?api_key=secret-value"},
        )

    assert exc_info.value.details["url"] == "https://evil.example.com"
    assert "secret-value" not in str(exc_info.value.details)


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


def test_egress_policy_uses_registered_scope_policy_provider(ctx, monkeypatch):
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", [])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    _reset_policy_cache(monkeypatch)
    egress.reset_egress_scope_policy_provider()
    egress.register_egress_scope_policy_provider(AllowApiExampleProvider())

    egress.check_egress_policy(
        ctx,
        "tool:http:test",
        {"url": "https://api.example.com/v1/health"},
    )

    egress.reset_egress_scope_policy_provider()


def test_egress_policy_provider_failure_denies_request(ctx, monkeypatch):
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["*.example.com"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    _reset_policy_cache(monkeypatch)
    egress.reset_egress_scope_policy_provider()
    egress.register_egress_scope_policy_provider(FailingScopePolicyProvider())

    with pytest.raises(ForbiddenError, match="lookup"):
        egress.check_egress_policy(
            ctx,
            "tool:http:test",
            {"url": "https://api.example.com/v1/health"},
        )

    egress.reset_egress_scope_policy_provider()


def test_egress_policy_denies_private_ip_even_when_allowlisted(ctx, monkeypatch):
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["127.0.0.1"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    _reset_policy_cache(monkeypatch)

    with pytest.raises(ForbiddenError):
        egress.check_egress_policy(
            ctx,
            "knowledge:crawler",
            {"url": "http://127.0.0.1/admin"},
        )


def test_egress_policy_cannot_be_bypassed_with_uppercase_scheme(ctx, monkeypatch):
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["allowed.example.com"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    _reset_policy_cache(monkeypatch)

    with pytest.raises(ForbiddenError):
        egress.check_egress_policy(
            ctx,
            "knowledge:crawler",
            {"url": "HTTPS://evil.example.com/guide"},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "address",
    [
        "10.0.0.2",
        "127.0.0.1",
        "169.254.169.254",
        "::1",
        "fc00::10",
    ],
)
async def test_governed_egress_guard_rejects_non_public_dns_targets(
    ctx: RequestContext,
    monkeypatch: pytest.MonkeyPatch,
    address: str,
) -> None:
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["service.example.com"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    _reset_policy_cache(monkeypatch)

    guard = egress.GovernedEgressGuard(
        address_resolver=StaticAddressResolver([address])
    )

    with pytest.raises(ForbiddenError, match="non-public"):
        await guard.authorize(
            ctx,
            "model-provider:test",
            "https://service.example.com/v1",
        )


@pytest.mark.asyncio
async def test_governed_egress_guard_checks_non_http_notification_host(
    ctx: RequestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["hooks.example.com"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    _reset_policy_cache(monkeypatch)

    guard = egress.GovernedEgressGuard(
        address_resolver=StaticAddressResolver(["169.254.169.254"])
    )

    with pytest.raises(ForbiddenError, match="non-public"):
        await guard.authorize(
            ctx,
            "notification:apprise",
            "json://hooks.example.com/notify",
            allow_non_http=True,
        )


@pytest.mark.asyncio
async def test_governed_egress_guard_maps_fixed_notification_provider_host(
    ctx: RequestContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["hooks.slack.com"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    _reset_policy_cache(monkeypatch)
    resolver = RecordingAddressResolver(["13.107.246.40"])

    await egress.GovernedEgressGuard(address_resolver=resolver).authorize(
        ctx,
        "notification:apprise",
        "slack://token-a/token-b/token-c",
        allow_non_http=True,
    )

    assert resolver.calls == [("hooks.slack.com", 443)]
