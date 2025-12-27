""" egress

Egress policy (deny-by-default for external calls).
"""

import re
from typing import Dict, Any, List, Optional, Set
from urllib.parse import urlparse
from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ForbiddenError
from app.kernel.config.settings import settings


class EgressPolicy:
    """Egress policy checker with allowlist/blocklist support."""
    
    def __init__(
        self,
        global_allowlist: Optional[List[str]] = None,
        global_blocklist: Optional[List[str]] = None,
    ):
        """Initialize egress policy.
        
        Args:
            global_allowlist: Global allowed domains (wildcards supported).
            global_blocklist: Global blocked domains (wildcards supported).
        """
        self.global_allowlist: Set[str] = set(global_allowlist or [])
        self.global_blocklist: Set[str] = set(global_blocklist or [])
        # Cache compiled patterns
        self._allowlist_patterns: List[re.Pattern] = [
            self._compile_pattern(pattern) for pattern in self.global_allowlist
        ]
        self._blocklist_patterns: List[re.Pattern] = [
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
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL.
        
        Args:
            url: URL string.
            
        Returns:
            Domain name or None if invalid.
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path.split("/")[0]
            # Remove port if present
            if ":" in domain:
                domain = domain.split(":")[0]
            return domain.lower() if domain else None
        except Exception:
            return None
    
    def _matches_pattern(self, domain: str, patterns: List[re.Pattern]) -> bool:
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
    
    async def check_allowed(
        self,
        ctx: RequestContext,
        url: str,
        workspace_allowlist: Optional[List[str]] = None,
        tenant_allowlist: Optional[List[str]] = None,
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
_egress_policy: Optional[EgressPolicy] = None


def get_egress_policy() -> EgressPolicy:
    """Get or create global egress policy instance.
    
    Returns:
        EgressPolicy instance.
    """
    global _egress_policy
    if _egress_policy is None:
        # Initialize with default allowlist (can be configured via settings)
        # For now, allow common public APIs
        default_allowlist = [
            "*.openai.com",
            "*.anthropic.com",
            "*.googleapis.com",
            "api.github.com",
            "*.github.com",
        ]
        _egress_policy = EgressPolicy(
            global_allowlist=default_allowlist,
        )
    return _egress_policy


def check_egress_policy(
    ctx: RequestContext,
    resource_ref: str,
    parameters: Dict[str, Any],
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
    
    # Check if it's an external URL
    if not (url.startswith("http://") or url.startswith("https://")):
        # Not an HTTP URL, allow (might be internal resource)
        return
    
    # Get egress policy
    policy = get_egress_policy()
    
    # TODO: Load workspace/tenant allowlist from database
    # For now, use global policy only
    is_allowed = policy.check_allowed(
        ctx=ctx,
        url=url,
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
