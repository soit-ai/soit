"""OAuth 2.1 authorization for protected MCP servers.

Implements the discovery and token-request half of the MCP authorization
specification: Protected Resource Metadata (RFC 9728) to find the authorization
server, authorization server metadata (RFC 8414 / OpenID Connect Discovery) to
find its token endpoint, and Resource Indicators (RFC 8707) so the issued token
is bound to the MCP server it will be presented to.

Only the ``client_credentials`` grant is implemented. SOIT calls MCP servers on
its own behalf from a worker, with no user-agent to redirect and no resource
owner present, so the authorization-code flow has no meaningful place here yet;
it needs a browser round trip, a callback route and per-user token storage.

Every request goes through the governed egress client, so an authorization
server is subject to the same egress policy as any other outbound destination.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.adapters.http.governed_client import governed_httpx_client
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.secrets.interface import SecretsPort
from app.kernel.security.egress import GovernedEgressGuard

logger = logging.getLogger(__name__)

PROTECTED_RESOURCE_PATH = "/.well-known/oauth-protected-resource"
AS_METADATA_PATHS = (
    "/.well-known/oauth-authorization-server",
    "/.well-known/openid-configuration",
)
TOKEN_EXPIRY_SKEW_SECONDS = 30
"""Refresh slightly early so a token cannot expire mid-request."""

_RESOURCE_METADATA_RE = re.compile(r'resource_metadata\s*=\s*"([^"]+)"', re.IGNORECASE)
_SCOPE_RE = re.compile(r'scope\s*=\s*"([^"]+)"', re.IGNORECASE)


class MCPAuthorizationError(Exception):
    """Authorization could not be established with the MCP server."""


@dataclass(frozen=True)
class ResourceChallenge:
    """What a 401 from an MCP server told us about how to authorize."""

    resource_metadata_url: str | None = None
    scopes: tuple[str, ...] = ()


@dataclass(frozen=True)
class AccessToken:
    """A bearer token and the moment it stops being usable."""

    value: str
    expires_at: float | None = None

    def is_valid(self, *, now: float | None = None) -> bool:
        if self.expires_at is None:
            return True
        moment = time.time() if now is None else now
        return moment < self.expires_at - TOKEN_EXPIRY_SKEW_SECONDS


def canonical_resource_uri(endpoint: str) -> str:
    """Return the RFC 8707 resource identifier for an MCP endpoint.

    The identifier must be an absolute URI without a fragment. A trailing slash
    is dropped because the specification asks implementations to be consistent,
    and servers commonly advertise the bare form.
    """
    parsed = urlparse(endpoint)
    if not parsed.scheme or not parsed.netloc:
        raise MCPAuthorizationError(
            "MCP endpoint must be an absolute URI to be used as a resource indicator"
        )
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"


def parse_resource_challenge(www_authenticate: str | None) -> ResourceChallenge:
    """Read the resource metadata URL and required scopes from a challenge."""
    if not www_authenticate:
        return ResourceChallenge()
    metadata_match = _RESOURCE_METADATA_RE.search(www_authenticate)
    scope_match = _SCOPE_RE.search(www_authenticate)
    scopes = tuple(scope_match.group(1).split()) if scope_match else ()
    return ResourceChallenge(
        resource_metadata_url=metadata_match.group(1) if metadata_match else None,
        scopes=scopes,
    )


def default_resource_metadata_url(endpoint: str) -> str:
    """Where protected resource metadata lives when no challenge pointed at it."""
    parsed = urlparse(endpoint)
    return urljoin(f"{parsed.scheme}://{parsed.netloc}", PROTECTED_RESOURCE_PATH)


class MCPOAuthClient:
    """Discover an MCP server's authorization server and obtain access tokens."""

    def __init__(
        self,
        *,
        ctx: RequestContext,
        egress_guard: GovernedEgressGuard | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.ctx = ctx
        self.egress_guard = egress_guard or GovernedEgressGuard()
        self.timeout = timeout
        self._tokens: dict[tuple[str, str], AccessToken] = {}

    def _client(self, resource_ref: str) -> httpx.AsyncClient:
        return governed_httpx_client(
            ctx=self.ctx,
            resource_ref=resource_ref,
            egress_guard=self.egress_guard,
            timeout=httpx.Timeout(self.timeout),
        )

    async def _get_json(self, url: str, *, resource_ref: str) -> dict[str, Any]:
        async with self._client(resource_ref) as client:
            response = await client.get(url, headers={"Accept": "application/json"})
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise MCPAuthorizationError(f"Metadata at {url} is not a JSON object")
        return payload

    async def discover_authorization_servers(
        self,
        *,
        endpoint: str,
        challenge: ResourceChallenge,
    ) -> tuple[list[str], tuple[str, ...]]:
        """Return the authorization server issuers advertised for this MCP server."""
        metadata_url = challenge.resource_metadata_url or default_resource_metadata_url(
            endpoint
        )
        metadata = await self._get_json(
            metadata_url, resource_ref="mcp:protected-resource-metadata"
        )
        issuers = [
            str(item)
            for item in (metadata.get("authorization_servers") or [])
            if str(item or "").strip()
        ]
        if not issuers:
            raise MCPAuthorizationError(
                "Protected resource metadata advertises no authorization server"
            )
        supported = tuple(
            str(item) for item in (metadata.get("scopes_supported") or []) if item
        )
        return issuers, supported

    async def discover_token_endpoint(self, issuer: str) -> str:
        """Return the token endpoint from authorization server metadata."""
        base = issuer.rstrip("/")
        last_error: Exception | None = None
        for path in AS_METADATA_PATHS:
            try:
                metadata = await self._get_json(
                    f"{base}{path}", resource_ref="mcp:authorization-server-metadata"
                )
            except Exception as exc:
                last_error = exc
                continue
            token_endpoint = str(metadata.get("token_endpoint") or "").strip()
            if token_endpoint:
                return token_endpoint
            last_error = MCPAuthorizationError(
                f"Authorization server metadata at {base}{path} has no token_endpoint"
            )
        raise MCPAuthorizationError(
            f"Could not discover a token endpoint for {issuer}: {last_error}"
        )

    async def _request_token(
        self,
        *,
        token_endpoint: str,
        client_id: str,
        client_secret: str,
        resource: str,
        scopes: tuple[str, ...],
    ) -> AccessToken:
        form: dict[str, str] = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            # RFC 8707: bind the token to the MCP server it will be sent to, so
            # it cannot be replayed against a different resource.
            "resource": resource,
        }
        if scopes:
            form["scope"] = " ".join(scopes)

        async with self._client("mcp:token-endpoint") as client:
            response = await client.post(token_endpoint, data=form)
            if response.status_code >= 400:
                raise MCPAuthorizationError(
                    f"Token request rejected with HTTP {response.status_code}"
                )
            payload = response.json()

        if not isinstance(payload, dict):
            raise MCPAuthorizationError("Token response is not a JSON object")
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise MCPAuthorizationError("Token response contained no access_token")
        expires_in = payload.get("expires_in")
        expires_at = (
            time.time() + float(expires_in)
            if isinstance(expires_in, int | float)
            else None
        )
        return AccessToken(value=token, expires_at=expires_at)

    async def get_access_token(
        self,
        *,
        server_key: str,
        endpoint: str,
        auth_config: dict[str, Any],
        secrets_port: SecretsPort | None,
        challenge: ResourceChallenge | None = None,
        force_refresh: bool = False,
    ) -> str:
        """Return a bearer token for this MCP server, discovering as needed."""
        resource = canonical_resource_uri(endpoint)
        cache_key = (server_key, resource)
        if not force_refresh:
            cached = self._tokens.get(cache_key)
            if cached is not None and cached.is_valid():
                return cached.value

        client_id = str(auth_config.get("client_id") or "").strip()
        if not client_id:
            raise MCPAuthorizationError("MCP OAuth requires client_id")
        if "client_secret" in auth_config:
            raise MCPAuthorizationError("MCP credentials must use client_secret_id")
        secret_id = auth_config.get("client_secret_id")
        if not secret_id:
            raise MCPAuthorizationError("MCP OAuth requires client_secret_id")
        if secrets_port is None:
            raise MCPAuthorizationError("MCP OAuth requires a secrets port")
        client_secret = await secrets_port.get_secret(secret_id=str(secret_id))

        effective_challenge = challenge or ResourceChallenge()
        configured_issuer = str(auth_config.get("issuer") or "").strip()
        if configured_issuer:
            issuers = [configured_issuer]
            supported_scopes: tuple[str, ...] = ()
        else:
            issuers, supported_scopes = await self.discover_authorization_servers(
                endpoint=endpoint,
                challenge=effective_challenge,
            )

        configured_scopes = tuple(
            str(item) for item in (auth_config.get("scopes") or []) if item
        )
        # The challenge is authoritative for the current operation; fall back to
        # what the deployment configured, then to what the resource advertises.
        scopes = effective_challenge.scopes or configured_scopes or supported_scopes

        token_endpoint = str(auth_config.get("token_endpoint") or "").strip()
        if not token_endpoint:
            token_endpoint = await self.discover_token_endpoint(issuers[0])

        token = await self._request_token(
            token_endpoint=token_endpoint,
            client_id=client_id,
            client_secret=client_secret,
            resource=resource,
            scopes=scopes,
        )
        self._tokens[cache_key] = token
        return token.value

    def invalidate(self, *, server_key: str, endpoint: str) -> None:
        """Drop a cached token, e.g. after the server rejected it."""
        self._tokens.pop((server_key, canonical_resource_uri(endpoint)), None)
