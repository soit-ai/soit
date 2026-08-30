""" egress

Egress policy (deny-by-default for external calls).
"""

import asyncio
import ipaddress
import logging
import re
import socket
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse

from app.kernel.commons.errors import ForbiddenError, KernelError
from app.kernel.contracts.context import RequestContext
from app.settings.settings import settings

logger = logging.getLogger(__name__)

EGRESS_BLOCK_EVENT_TYPE = "security.egress.blocked"
"""Audit event type for an outbound request the policy refused.

Shared by the recorder that writes it and the surfaces that count it, so the
two cannot drift apart on a string literal.
"""


@dataclass(frozen=True)
class EgressScopePolicy:
    """Tenant/workspace scoped egress policy lists."""

    tenant_allowlist: list[str] = field(default_factory=list)
    tenant_blocklist: list[str] = field(default_factory=list)
    workspace_allowlist: list[str] = field(default_factory=list)
    workspace_blocklist: list[str] = field(default_factory=list)


class EgressScopePolicyProvider(Protocol):
    """Provider boundary for tenant/workspace egress policy lookup."""

    def get_scope_policy(self, ctx: RequestContext) -> EgressScopePolicy:
        """Return scoped egress policy for the request context."""


class AddressResolver(Protocol):
    """Resolve the addresses an outbound client may connect to."""

    async def resolve(self, hostname: str, port: int) -> list[str]:
        """Return every address resolved for the target host."""


class SocketAddressResolver:
    """Resolve outbound targets through the operating system resolver."""

    async def resolve(self, hostname: str, port: int) -> list[str]:
        """Resolve a hostname without blocking the event loop."""
        loop = asyncio.get_running_loop()
        records = await loop.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
        return sorted({str(record[4][0]) for record in records})


class EgressBlockRecorder(Protocol):
    """Sink for outbound requests the policy refused."""

    def record_block(
        self,
        ctx: RequestContext,
        *,
        resource_ref: str,
        url: str | None,
        domain: str | None,
        reason: str,
    ) -> None:
        """Persist one refusal. Must not raise: the refusal itself is the point."""


_egress_scope_policy_provider: EgressScopePolicyProvider | None = None
_egress_block_recorder: EgressBlockRecorder | None = None


def register_egress_block_recorder(recorder: EgressBlockRecorder) -> None:
    """Register the process-wide sink for refused outbound requests."""

    global _egress_block_recorder
    _egress_block_recorder = recorder


def reset_egress_block_recorder() -> None:
    """Clear the process-wide egress block recorder."""

    global _egress_block_recorder
    _egress_block_recorder = None


def record_egress_block(
    ctx: RequestContext,
    *,
    resource_ref: str,
    url: str | None,
    domain: str | None,
    reason: str,
) -> None:
    """Record a refused outbound request, if a sink is registered.

    Recording must never change the outcome: a policy that fails closed has
    already decided, and losing the evidence is better than turning a refusal
    into a crash. Failures are logged and swallowed.
    """
    recorder = _egress_block_recorder
    if recorder is None:
        return
    try:
        recorder.record_block(
            ctx,
            resource_ref=resource_ref,
            url=url,
            domain=domain,
            reason=reason,
        )
    except Exception:
        logger.warning("Failed to record an egress block", exc_info=True)


def register_egress_scope_policy_provider(provider: EgressScopePolicyProvider) -> None:
    """Register the process-wide egress scope policy provider."""

    global _egress_scope_policy_provider
    _egress_scope_policy_provider = provider


def reset_egress_scope_policy_provider() -> None:
    """Clear the process-wide egress scope policy provider."""

    global _egress_scope_policy_provider
    _egress_scope_policy_provider = None


def get_egress_scope_policy_provider() -> EgressScopePolicyProvider | None:
    """Return the registered egress scope policy provider, if any."""

    return _egress_scope_policy_provider


class EgressPolicy:
    """Egress policy checker with allowlist/blocklist support."""

    def __init__(
        self,
        global_allowlist: list[str] | None = None,
        global_blocklist: list[str] | None = None,
    ):
        """Initialize egress policy.

        Args:
            global_allowlist: Global allowed domains (wildcards supported).
            global_blocklist: Global blocked domains (wildcards supported).
        """
        self.global_allowlist: set[str] = set(global_allowlist or [])
        self.global_blocklist: set[str] = set(global_blocklist or [])
        # Cache compiled patterns
        self._allowlist_patterns: list[re.Pattern] = [
            self._compile_pattern(pattern) for pattern in self.global_allowlist
        ]
        self._blocklist_patterns: list[re.Pattern] = [
            self._compile_pattern(pattern) for pattern in self.global_blocklist
        ]

    def _compile_pattern(self, pattern: str) -> re.Pattern:
        """Compile domain pattern to regex.

        Args:
            pattern: Domain pattern (supports wildcards like *.example.com).

        Returns:
            Compiled regex pattern.
        """
        # Escape special characters except *
        escaped = re.escape(pattern)
        # Replace \* with .*
        regex = escaped.replace("\\*", ".*")
        # Match entire domain
        return re.compile(f"^{regex}$", re.IGNORECASE)

    def _extract_domain(self, url: str) -> str | None:
        """Extract domain from URL.

        Args:
            url: URL string.

        Returns:
            Domain name or None if invalid.
        """
        try:
            parsed = urlparse(url)
            domain = parsed.hostname or parsed.path.split("/")[0]
            return domain.lower() if domain else None
        except Exception:
            return None

    @staticmethod
    def _is_public_endpoint(domain: str) -> bool:
        """Return False for localhost and non-global IP literals."""
        if domain.rstrip(".").lower() == "localhost":
            return False
        try:
            return ipaddress.ip_address(domain).is_global
        except ValueError:
            return True

    def _matches_pattern(self, domain: str, patterns: list[re.Pattern]) -> bool:
        """Check if domain matches any pattern.

        Args:
            domain: Domain name.
            patterns: List of compiled regex patterns.

        Returns:
            True if matches any pattern.
        """
        for pattern in patterns:
            if pattern.match(domain):
                return True
        return False

    def check_allowed(
        self,
        ctx: RequestContext,
        url: str,
        workspace_allowlist: list[str] | None = None,
        tenant_allowlist: list[str] | None = None,
    ) -> bool:
        """Check if URL is allowed by egress policy.

        Args:
            ctx: Request context.
            url: URL to check.
            workspace_allowlist: Optional workspace-specific allowlist.
            tenant_allowlist: Optional tenant-specific allowlist.

        Returns:
            True if allowed, False if denied.
        """
        if not settings.enable_egress_policy:
            return True

        domain = self._extract_domain(url)
        if not domain:
            # Invalid URL, deny by default
            return False
        if not self._is_public_endpoint(domain):
            return False

        # Check blocklist first (highest priority)
        if self._blocklist_patterns and self._matches_pattern(domain, self._blocklist_patterns):
            return False

        # Check tenant allowlist
        if tenant_allowlist:
            tenant_patterns = [self._compile_pattern(p) for p in tenant_allowlist]
            if self._matches_pattern(domain, tenant_patterns):
                return True

        # Check workspace allowlist
        if workspace_allowlist:
            workspace_patterns = [self._compile_pattern(p) for p in workspace_allowlist]
            if self._matches_pattern(domain, workspace_patterns):
                return True

        # Check global allowlist
        if self._allowlist_patterns and self._matches_pattern(domain, self._allowlist_patterns):
            return True

        # Deny by default if no allowlist matches
        # If global allowlist is empty, deny all external URLs
        if not self.global_allowlist and not workspace_allowlist and not tenant_allowlist:
            return False

        # If allowlist exists but no match, deny
        return False


# Global egress policy instance
_egress_policy: EgressPolicy | None = None


def get_egress_policy() -> EgressPolicy:
    """Get or create global egress policy instance.

    Returns:
        EgressPolicy instance.
    """
    global _egress_policy
    if _egress_policy is None:
        default_allowlist = settings.egress_allowlist
        default_blocklist = settings.egress_blocklist
        _egress_policy = EgressPolicy(
            global_allowlist=default_allowlist,
            global_blocklist=default_blocklist,
        )
    return _egress_policy


def check_egress_policy(
    ctx: RequestContext,
    resource_ref: str,
    parameters: dict[str, Any],
) -> None:
    """Check egress policy (deny-by-default).

    Args:
        ctx: Request context.
        resource_ref: Resource reference (tool_ref, endpoint, etc.).
        parameters: Request parameters (may contain URLs).

    Raises:
        ForbiddenError: If egress is denied.
    """
    if not settings.enable_egress_policy:
        return

    # Extract URL from parameters
    url = parameters.get("url") or parameters.get("endpoint") or parameters.get("uri")
    if not url:
        # No URL in parameters, allow (might be a function call without HTTP)
        return

    # Check if it's an external URL without relying on case-sensitive prefixes.
    scheme = urlparse(str(url)).scheme.lower()
    if scheme not in {"http", "https"}:
        # Not an HTTP URL, allow (might be internal resource)
        return

    parsed_url = urlparse(str(url))
    hostname = parsed_url.hostname
    if hostname:
        host = f"[{hostname}]" if ":" in hostname else hostname
        try:
            port = parsed_url.port
        except ValueError:
            port = None
        url = f"{scheme}://{host}{f':{port}' if port is not None else ''}"

    # Get egress policy
    policy = get_egress_policy()

    tenant_allowlist: list[str] | None = None
    tenant_blocklist: list[str] | None = None
    workspace_allowlist: list[str] | None = None
    workspace_blocklist: list[str] | None = None

    provider = get_egress_scope_policy_provider()
    if provider is not None:
        try:
            scope_policy = provider.get_scope_policy(ctx)
            tenant_allowlist = list(scope_policy.tenant_allowlist or [])
            tenant_blocklist = list(scope_policy.tenant_blocklist or [])
            workspace_allowlist = list(scope_policy.workspace_allowlist or [])
            workspace_blocklist = list(scope_policy.workspace_blocklist or [])
        except Exception as exc:
            record_egress_block(
                ctx,
                resource_ref=resource_ref,
                url=str(url),
                domain=None,
                reason="policy_lookup_failed",
            )
            raise ForbiddenError(
                "Egress policy lookup failed; request denied",
                {"resource_ref": resource_ref},
            ) from exc

    domain = policy._extract_domain(url)
    if domain:
        if tenant_blocklist:
            tenant_patterns = [policy._compile_pattern(p) for p in tenant_blocklist]
            if policy._matches_pattern(domain, tenant_patterns):
                record_egress_block(
                    ctx,
                    resource_ref=resource_ref,
                    url=str(url),
                    domain=domain,
                    reason="tenant_blocklist",
                )
                raise ForbiddenError(
                    f"Egress to {domain} is blocked by tenant policy",
                    {
                        "url": url,
                        "domain": domain,
                        "resource_ref": resource_ref,
                    },
                )
        if workspace_blocklist:
            workspace_patterns = [policy._compile_pattern(p) for p in workspace_blocklist]
            if policy._matches_pattern(domain, workspace_patterns):
                record_egress_block(
                    ctx,
                    resource_ref=resource_ref,
                    url=str(url),
                    domain=domain,
                    reason="workspace_blocklist",
                )
                raise ForbiddenError(
                    f"Egress to {domain} is blocked by workspace policy",
                    {
                        "url": url,
                        "domain": domain,
                        "resource_ref": resource_ref,
                    },
                )

    is_allowed = policy.check_allowed(
        ctx=ctx,
        url=url,
        workspace_allowlist=workspace_allowlist,
        tenant_allowlist=tenant_allowlist,
    )

    if not is_allowed:
        domain = policy._extract_domain(url)
        record_egress_block(
            ctx,
            resource_ref=resource_ref,
            url=str(url),
            domain=domain,
            reason="not_allowlisted",
        )
        raise ForbiddenError(
            f"Egress to {domain} is not allowed by policy",
            {
                "url": url,
                "domain": domain,
                "resource_ref": resource_ref,
            }
        )


def iter_http_urls(value: Any) -> list[str]:
    """Return every HTTP(S) URL nested in a transport payload."""
    urls: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            urls.extend(iter_http_urls(item))
    elif isinstance(value, list | tuple):
        for item in value:
            urls.extend(iter_http_urls(item))
    elif isinstance(value, str):
        try:
            scheme = urlparse(value).scheme.lower()
        except ValueError:
            scheme = ""
        if scheme in {"http", "https"}:
            urls.append(value)
    return urls


_NON_HTTP_DEFAULT_PORTS = {
    "discord": 443,
    "discords": 443,
    "form": 80,
    "forms": 443,
    "json": 80,
    "jsons": 443,
    "mailto": 25,
    "smtp": 25,
    "smtps": 465,
    "telegram": 443,
    "xml": 80,
    "xmls": 443,
}

_NON_HTTP_FIXED_HOSTS = {
    "discord": "discord.com",
    "discords": "discord.com",
    "slack": "hooks.slack.com",
    "slacks": "hooks.slack.com",
    "telegram": "api.telegram.org",
}


class GovernedEgressGuard:
    """Authorize an outbound target against scope policy and resolved addresses."""

    def __init__(self, address_resolver: AddressResolver | None = None) -> None:
        self.address_resolver = address_resolver or SocketAddressResolver()

    @staticmethod
    def _policy_url(
        hostname: str,
        port: int | None,
        *,
        scheme: str = "https",
    ) -> str:
        host = f"[{hostname}]" if ":" in hostname else hostname
        suffix = f":{port}" if port is not None else ""
        return f"{scheme}://{host}{suffix}"

    async def authorize(
        self,
        ctx: RequestContext,
        resource_ref: str,
        url: str,
        *,
        allow_non_http: bool = False,
    ) -> None:
        """Fail closed unless the target is allowed and resolves only publicly."""
        try:
            parsed = urlparse(str(url))
            scheme = parsed.scheme.lower()
            hostname = parsed.hostname
            parsed_port = parsed.port
        except ValueError as exc:
            raise KernelError(
                "EGRESS_INVALID_TARGET",
                "Outbound target is not a valid URL",
            ) from exc

        if scheme not in {"http", "https"}:
            if not allow_non_http or (
                scheme not in _NON_HTTP_DEFAULT_PORTS
                and scheme not in _NON_HTTP_FIXED_HOSTS
            ):
                raise ForbiddenError(
                    "Outbound target scheme is not allowed",
                    {"resource_ref": resource_ref, "scheme": scheme or None},
                )
        hostname = _NON_HTTP_FIXED_HOSTS.get(scheme, hostname)
        if not hostname:
            raise KernelError(
                "EGRESS_INVALID_TARGET",
                "Outbound target must include a hostname",
            )
        if scheme in {"http", "https"} and (parsed.username or parsed.password):
            raise ForbiddenError(
                "Authenticated outbound HTTP URLs are not allowed",
                {"resource_ref": resource_ref},
            )

        port = parsed_port or (
            443
            if scheme == "https"
            else 80
            if scheme == "http"
            else _NON_HTTP_DEFAULT_PORTS.get(scheme, 443)
        )
        policy_url = self._policy_url(
            hostname,
            parsed_port,
            scheme=scheme if scheme in {"http", "https"} else "https",
        )
        check_egress_policy(ctx, resource_ref, {"url": policy_url})

        try:
            addresses = await self.address_resolver.resolve(hostname, port)
        except Exception as exc:
            raise KernelError(
                "EGRESS_DNS_FAILED",
                "Outbound target DNS resolution failed",
                {"resource_ref": resource_ref, "hostname": hostname},
            ) from exc
        if not addresses:
            raise KernelError(
                "EGRESS_DNS_FAILED",
                "Outbound target did not resolve",
                {"resource_ref": resource_ref, "hostname": hostname},
            )

        for address in addresses:
            try:
                is_public = ipaddress.ip_address(address).is_global
            except ValueError as exc:
                raise KernelError(
                    "EGRESS_DNS_FAILED",
                    "Outbound target resolved to an invalid address",
                    {"resource_ref": resource_ref, "hostname": hostname},
                ) from exc
            if not is_public:
                record_egress_block(
                    ctx,
                    resource_ref=resource_ref,
                    url=policy_url,
                    domain=hostname,
                    reason="non_public_address",
                )
                raise ForbiddenError(
                    "Outbound target resolves to a private or non-public address",
                    {
                        "resource_ref": resource_ref,
                        "hostname": hostname,
                        "address": address,
                    },
                )
