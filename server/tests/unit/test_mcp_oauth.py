"""OAuth authorization for protected MCP servers."""

from typing import Any

import pytest

from app.adapters.tools import mcp_oauth
from app.adapters.tools.mcp_oauth import (
    AccessToken,
    MCPAuthorizationError,
    MCPOAuthClient,
    ResourceChallenge,
    canonical_resource_uri,
    default_resource_metadata_url,
    parse_resource_challenge,
)
from app.kernel.contracts.context import RequestContext

ENDPOINT = "https://mcp.example.com/mcp"


class _StubSecrets:
    def __init__(self, value: str = "s3cret") -> None:
        self.value = value
        self.requested: list[str] = []

    async def get_secret(self, *, secret_id: str) -> str:
        self.requested.append(secret_id)
        return self.value


def _ctx() -> RequestContext:
    return RequestContext(tenant_id="t", workspace_id="w", user_id="u")


def _client(monkeypatch, *, metadata: dict[str, Any], token_calls: list[dict]) -> MCPOAuthClient:
    client = MCPOAuthClient(ctx=_ctx())

    async def fake_get_json(url: str, **_: Any) -> dict[str, Any]:
        if url not in metadata:
            raise MCPAuthorizationError(f"no metadata stubbed for {url}")
        return metadata[url]

    async def fake_request_token(**kwargs: Any) -> AccessToken:
        token_calls.append(kwargs)
        return AccessToken(value="tok-123", expires_at=None)

    monkeypatch.setattr(client, "_get_json", fake_get_json)
    monkeypatch.setattr(client, "_request_token", fake_request_token)
    return client


def test_canonical_resource_uri_normalises_the_endpoint():
    assert canonical_resource_uri("HTTPS://MCP.Example.com/mcp/") == (
        "https://mcp.example.com/mcp"
    )
    assert canonical_resource_uri("https://mcp.example.com") == "https://mcp.example.com"


def test_a_relative_endpoint_cannot_be_a_resource_indicator():
    with pytest.raises(MCPAuthorizationError, match="absolute URI"):
        canonical_resource_uri("mcp.example.com/mcp")


def test_challenge_carries_the_metadata_url_and_required_scopes():
    challenge = parse_resource_challenge(
        'Bearer resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource", '
        'scope="files:read files:write"'
    )

    assert challenge.resource_metadata_url == (
        "https://mcp.example.com/.well-known/oauth-protected-resource"
    )
    assert challenge.scopes == ("files:read", "files:write")


def test_a_missing_challenge_falls_back_to_the_well_known_location():
    assert parse_resource_challenge(None) == ResourceChallenge()
    assert default_resource_metadata_url(ENDPOINT) == (
        "https://mcp.example.com/.well-known/oauth-protected-resource"
    )


@pytest.mark.asyncio
async def test_token_is_discovered_through_protected_resource_metadata(monkeypatch):
    token_calls: list[dict] = []
    client = _client(
        monkeypatch,
        metadata={
            "https://mcp.example.com/.well-known/oauth-protected-resource": {
                "authorization_servers": ["https://auth.example.com"],
                "scopes_supported": ["files:read"],
            },
            "https://auth.example.com/.well-known/oauth-authorization-server": {
                "token_endpoint": "https://auth.example.com/token",
            },
        },
        token_calls=token_calls,
    )
    secrets = _StubSecrets()

    token = await client.get_access_token(
        server_key="files",
        endpoint=ENDPOINT,
        auth_config={"client_id": "soit", "client_secret_id": "sec_1"},
        secrets_port=secrets,
    )

    assert token == "tok-123"
    assert token_calls[0]["token_endpoint"] == "https://auth.example.com/token"
    # RFC 8707: the token must be bound to the MCP server it will be sent to.
    assert token_calls[0]["resource"] == "https://mcp.example.com/mcp"
    assert token_calls[0]["scopes"] == ("files:read",)
    assert secrets.requested == ["sec_1"]


@pytest.mark.asyncio
async def test_openid_discovery_is_tried_when_oauth_metadata_is_absent(monkeypatch):
    token_calls: list[dict] = []
    client = _client(
        monkeypatch,
        metadata={
            "https://mcp.example.com/.well-known/oauth-protected-resource": {
                "authorization_servers": ["https://auth.example.com"],
            },
            "https://auth.example.com/.well-known/openid-configuration": {
                "token_endpoint": "https://auth.example.com/oidc/token",
            },
        },
        token_calls=token_calls,
    )

    await client.get_access_token(
        server_key="files",
        endpoint=ENDPOINT,
        auth_config={"client_id": "soit", "client_secret_id": "sec_1"},
        secrets_port=_StubSecrets(),
    )

    assert token_calls[0]["token_endpoint"] == "https://auth.example.com/oidc/token"


@pytest.mark.asyncio
async def test_challenge_scopes_win_over_configured_scopes(monkeypatch):
    token_calls: list[dict] = []
    client = _client(
        monkeypatch,
        metadata={
            "https://mcp.example.com/.well-known/oauth-protected-resource": {
                "authorization_servers": ["https://auth.example.com"],
                "scopes_supported": ["files:read"],
            },
            "https://auth.example.com/.well-known/oauth-authorization-server": {
                "token_endpoint": "https://auth.example.com/token",
            },
        },
        token_calls=token_calls,
    )

    await client.get_access_token(
        server_key="files",
        endpoint=ENDPOINT,
        auth_config={
            "client_id": "soit",
            "client_secret_id": "sec_1",
            "scopes": ["files:read"],
        },
        # The server is authoritative about what this operation needs.
        challenge=ResourceChallenge(scopes=("files:write",)),
        secrets_port=_StubSecrets(),
    )

    assert token_calls[0]["scopes"] == ("files:write",)


@pytest.mark.asyncio
async def test_a_valid_token_is_reused_and_a_refresh_is_forced_on_demand(monkeypatch):
    token_calls: list[dict] = []
    client = _client(
        monkeypatch,
        metadata={
            "https://mcp.example.com/.well-known/oauth-protected-resource": {
                "authorization_servers": ["https://auth.example.com"],
            },
            "https://auth.example.com/.well-known/oauth-authorization-server": {
                "token_endpoint": "https://auth.example.com/token",
            },
        },
        token_calls=token_calls,
    )
    config = {"client_id": "soit", "client_secret_id": "sec_1"}

    await client.get_access_token(
        server_key="files", endpoint=ENDPOINT, auth_config=config, secrets_port=_StubSecrets()
    )
    await client.get_access_token(
        server_key="files", endpoint=ENDPOINT, auth_config=config, secrets_port=_StubSecrets()
    )
    assert len(token_calls) == 1

    await client.get_access_token(
        server_key="files",
        endpoint=ENDPOINT,
        auth_config=config,
        secrets_port=_StubSecrets(),
        force_refresh=True,
    )
    assert len(token_calls) == 2


def test_an_expiring_token_is_refreshed_before_it_actually_expires():
    token = AccessToken(value="t", expires_at=1_000.0)

    assert token.is_valid(now=1_000.0 - mcp_oauth.TOKEN_EXPIRY_SKEW_SECONDS - 1)
    # Inside the skew window the token is treated as unusable so it cannot
    # expire midway through a request.
    assert not token.is_valid(now=1_000.0 - mcp_oauth.TOKEN_EXPIRY_SKEW_SECONDS + 1)
    assert AccessToken(value="t").is_valid(now=10**9)


@pytest.mark.asyncio
async def test_an_inline_client_secret_is_refused(monkeypatch):
    client = _client(monkeypatch, metadata={}, token_calls=[])

    with pytest.raises(MCPAuthorizationError, match="client_secret_id"):
        await client.get_access_token(
            server_key="files",
            endpoint=ENDPOINT,
            auth_config={"client_id": "soit", "client_secret": "plaintext"},
            secrets_port=_StubSecrets(),
        )


@pytest.mark.asyncio
async def test_a_resource_advertising_no_authorization_server_is_an_error(monkeypatch):
    client = _client(
        monkeypatch,
        metadata={
            "https://mcp.example.com/.well-known/oauth-protected-resource": {
                "authorization_servers": [],
            }
        },
        token_calls=[],
    )

    with pytest.raises(MCPAuthorizationError, match="no authorization server"):
        await client.get_access_token(
            server_key="files",
            endpoint=ENDPOINT,
            auth_config={"client_id": "soit", "client_secret_id": "sec_1"},
            secrets_port=_StubSecrets(),
        )
