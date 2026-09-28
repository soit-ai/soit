"""EGRESS_PRIVATE_NETWORKS opens named private networks, and nothing else, to governed calls."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.kernel.commons.errors import ForbiddenError
from app.kernel.security import egress
from app.settings.settings import Settings, settings


class _Resolver:
    def __init__(self, *addresses: str) -> None:
        self.addresses = list(addresses)

    async def resolve(self, hostname: str, port: int) -> list[str]:
        return self.addresses


@pytest.fixture
def policy(monkeypatch: pytest.MonkeyPatch):
    def configure(*, allowlist: list[str], networks: list[str]) -> None:
        monkeypatch.setattr(settings, "enable_egress_policy", True)
        monkeypatch.setattr(settings, "egress_allowlist", allowlist)
        monkeypatch.setattr(settings, "egress_blocklist", [])
        monkeypatch.setattr(settings, "egress_private_networks", networks)
        monkeypatch.setattr(egress, "_egress_policy", None)

    return configure


@pytest.mark.asyncio
async def test_a_private_address_stays_refused_by_default(ctx, policy) -> None:
    policy(allowlist=["127.0.0.1", "ollama.internal"], networks=[])

    with pytest.raises(ForbiddenError):
        await egress.check_egress_policy(ctx, "model:ollama", {"url": "http://127.0.0.1:11434/v1"})
    with pytest.raises(ForbiddenError, match="private or non-public"):
        await egress.GovernedEgressGuard(address_resolver=_Resolver("127.0.0.1")).authorize(
            ctx, "model:ollama", "http://ollama.internal:11434/v1"
        )


@pytest.mark.asyncio
async def test_an_opened_network_is_reachable_once_allowlisted(ctx, policy) -> None:
    policy(allowlist=["127.0.0.1", "vllm.internal"], networks=["127.0.0.1/32", "10.20.0.0/16"])

    await egress.GovernedEgressGuard(address_resolver=_Resolver("127.0.0.1")).authorize(
        ctx, "model:ollama", "http://127.0.0.1:11434/v1"
    )
    await egress.GovernedEgressGuard(address_resolver=_Resolver("10.20.3.4")).authorize(
        ctx, "model:vllm", "http://vllm.internal:8000/v1"
    )


@pytest.mark.asyncio
async def test_an_opened_network_still_needs_an_allowlist_entry(ctx, policy) -> None:
    policy(allowlist=["api.example.com"], networks=["127.0.0.1/32"])

    with pytest.raises(ForbiddenError):
        await egress.GovernedEgressGuard(address_resolver=_Resolver("127.0.0.1")).authorize(
            ctx, "model:ollama", "http://127.0.0.1:11434/v1"
        )


@pytest.mark.asyncio
async def test_other_private_addresses_stay_refused(ctx, policy) -> None:
    policy(allowlist=["*.internal", "169.254.169.254"], networks=["10.20.0.0/16"])

    # Metadata endpoints and other networks are not opened by opening one.
    with pytest.raises(ForbiddenError):
        await egress.check_egress_policy(ctx, "tool:http", {"url": "http://169.254.169.254/latest/meta-data"})
    # A name that resolves partly outside the opened network is refused.
    with pytest.raises(ForbiddenError, match="private or non-public"):
        await egress.GovernedEgressGuard(address_resolver=_Resolver("10.20.3.4", "192.168.1.9")).authorize(
            ctx, "model:vllm", "http://vllm.internal:8000/v1"
        )


def test_localhost_by_name_needs_both_loopback_addresses(policy) -> None:
    policy(allowlist=["localhost"], networks=["127.0.0.1/32"])
    assert egress.EgressPolicy._is_public_endpoint("localhost") is False

    policy(allowlist=["localhost"], networks=["127.0.0.1/32", "::1/128"])
    assert egress.EgressPolicy._is_public_endpoint("localhost") is True


@pytest.mark.parametrize("entry", ["not-a-network", "0.0.0.0/0", "::/0"])
def test_a_bad_or_everything_network_is_refused_at_startup(monkeypatch: pytest.MonkeyPatch, entry: str) -> None:
    monkeypatch.setenv("EGRESS_PRIVATE_NETWORKS", f'["{entry}"]')
    with pytest.raises(ValidationError, match="EGRESS_PRIVATE_NETWORKS"):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_networks_are_normalised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EGRESS_PRIVATE_NETWORKS", '["10.20.3.4/16", " 127.0.0.1 "]')
    assert Settings(_env_file=None).egress_private_networks == ["10.20.0.0/16", "127.0.0.1/32"]  # type: ignore[call-arg]
