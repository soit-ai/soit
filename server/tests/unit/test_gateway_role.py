"""A gateway process serves only the entry points external callers use."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.main import include_routes
from app.settings.settings import Settings


def _paths(role: str) -> set[str]:
    target = FastAPI()
    include_routes(target, role)
    return set(target.openapi()["paths"])


def test_a_gateway_serves_the_entry_points_and_health() -> None:
    paths = _paths("gateway")

    assert {"/v1/chat/completions", "/v1/models", "/v1/embeddings", "/v1/images/generations"} <= paths
    assert "/mcp" in paths
    assert any(path.startswith("/.well-known/") for path in paths)
    assert "/api/v1/tools/{tool_ref}/invoke" in paths
    assert {"/health/live", "/health/ready"} <= paths


def test_a_gateway_serves_nothing_of_the_consoles_api() -> None:
    allowed = ("/v1/", "/mcp", "/.well-known/", "/api/v1/tools", "/health", "/metrics")
    stray = [path for path in _paths("gateway") if not path.startswith(allowed)]
    assert stray == []
    assert not any(path.startswith(("/api/v1/agents", "/api/v1/workflows", "/api/v1/billing")) for path in _paths("gateway"))


def test_the_default_role_serves_everything_a_gateway_does() -> None:
    assert _paths("gateway") <= _paths("all")
    assert any(path.startswith("/api/v1/agents") for path in _paths("all"))


@pytest.mark.parametrize("value, role", [("gateway", "gateway"), (" Gateway ", "gateway"), ("ALL", "all")])
def test_the_role_is_read_from_soit_role(monkeypatch: pytest.MonkeyPatch, value: str, role: str) -> None:
    monkeypatch.setenv("SOIT_ROLE", value)
    assert Settings(_env_file=None).soit_role == role  # type: ignore[call-arg]


def test_an_unknown_role_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOIT_ROLE", "worker")
    with pytest.raises(ValidationError, match="SOIT_ROLE"):
        Settings(_env_file=None)  # type: ignore[call-arg]
