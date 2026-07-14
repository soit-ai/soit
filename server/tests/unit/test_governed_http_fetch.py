"""Tests for the governed HTTP fetch adapter."""

import httpx
import pytest

from app.adapters.http.governed_fetch import GovernedHttpFetchPort
from app.kernel.commons.errors import ForbiddenError
from app.kernel.security import egress
from app.settings.settings import settings
from app.wiring.container import Container
from app.wiring.services import build_knowledge_runtime_service


def test_container_provides_governed_http_fetch_port() -> None:
    container = Container()

    fetch_port = container.get_http_fetch_port()

    assert fetch_port is not None


def test_knowledge_runtime_is_wired_to_governed_fetch_port(db, ctx) -> None:
    service = build_knowledge_runtime_service(db=db, ctx=ctx)

    assert isinstance(service.http_fetch_port, GovernedHttpFetchPort)


@pytest.mark.asyncio
async def test_fetch_rejects_private_ip_before_network(ctx, monkeypatch) -> None:
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["127.0.0.1"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    monkeypatch.setattr(egress, "_egress_policy", None)

    with pytest.raises(ForbiddenError):
        await GovernedHttpFetchPort().fetch(
            ctx,
            "http://127.0.0.1/admin",
            max_bytes=1024,
        )


@pytest.mark.asyncio
async def test_fetch_rejects_hostname_resolving_to_private_ip(ctx, monkeypatch) -> None:
    class _PrivateResolver:
        async def resolve(self, hostname: str, port: int) -> list[str]:
            assert hostname == "docs.example.com"
            assert port == 443
            return ["10.0.0.10"]

    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["docs.example.com"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    monkeypatch.setattr(egress, "_egress_policy", None)

    with pytest.raises(ForbiddenError, match="private"):
        await GovernedHttpFetchPort(address_resolver=_PrivateResolver()).fetch(
            ctx,
            "https://docs.example.com/guide",
            max_bytes=1024,
        )


@pytest.mark.asyncio
async def test_fetch_streams_bounded_public_response(ctx, monkeypatch) -> None:
    class _PublicResolver:
        async def resolve(self, hostname: str, port: int) -> list[str]:
            return ["93.184.216.34"]

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=b"<html>public</html>",
        )

    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["docs.example.com"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    monkeypatch.setattr(egress, "_egress_policy", None)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    try:
        resource = await GovernedHttpFetchPort(
            address_resolver=_PublicResolver(),
            client=client,
        ).fetch(
            ctx,
            "https://docs.example.com/guide",
            max_bytes=1024,
        )
    finally:
        await client.aclose()

    assert resource.content == b"<html>public</html>"
    assert resource.content_type == "text/html"
    assert resource.final_url == "https://docs.example.com/guide"
    assert resource.status_code == 200


@pytest.mark.asyncio
async def test_fetch_revalidates_redirect_target_and_blocks_private_ip(
    ctx,
    monkeypatch,
) -> None:
    class _PublicResolver:
        async def resolve(self, hostname: str, port: int) -> list[str]:
            return ["93.184.216.34"]

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})

    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(
        settings,
        "egress_allowlist",
        ["docs.example.com", "127.0.0.1"],
    )
    monkeypatch.setattr(settings, "egress_blocklist", [])
    monkeypatch.setattr(egress, "_egress_policy", None)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    try:
        with pytest.raises(ForbiddenError):
            await GovernedHttpFetchPort(
                address_resolver=_PublicResolver(),
                client=client,
            ).fetch(
                ctx,
                "https://docs.example.com/guide",
                max_bytes=1024,
            )
    finally:
        await client.aclose()
