""" egress

Egress policy (deny-by-default for external calls).
"""

import ipaddress
import re
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse

from app.kernel.commons.errors import ForbiddenError
from app.kernel.contracts.context import RequestContext
from app.settings.settings import settings


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


_egress_scope_policy_provider: EgressScopePolicyProvider | None = None


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
            raise ForbiddenError(
                "Egress policy lookup failed; request denied",
                {"resource_ref": resource_ref},
            ) from exc

    domain = policy._extract_domain(url)
    if domain:
        if tenant_blocklist:
            tenant_patterns = [policy._compile_pattern(p) for p in tenant_blocklist]
            if policy._matches_pattern(domain, tenant_patterns):
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
        raise ForbiddenError(
            f"Egress to {domain} is not allowed by policy",
            {
                "url": url,
                "domain": domain,
                "resource_ref": resource_ref,
            }
        )
