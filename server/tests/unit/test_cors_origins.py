"""CORS_ALLOWED_ORIGINS: a wildcard never carries credentials."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import cors_origin_options


def test_a_wildcard_allows_any_origin_without_credentials() -> None:
    assert cors_origin_options(["*"]) == {"allow_origins": ["*"], "allow_credentials": False}


def test_named_origins_may_send_credentials() -> None:
    assert cors_origin_options([" https://console.example.com/ ", ""]) == {
        "allow_origins": ["https://console.example.com"],
        "allow_credentials": True,
    }


def test_an_empty_list_allows_no_origin() -> None:
    assert cors_origin_options([]) == {"allow_origins": [], "allow_credentials": False}


@pytest.mark.asyncio
async def test_the_default_does_not_echo_an_origin_with_credentials() -> None:
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.options(
            "/api/v1/health",
            headers={
                "Origin": "https://attacker.example",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )

    assert response.headers.get("access-control-allow-origin") == "*"
    assert "access-control-allow-credentials" not in response.headers
