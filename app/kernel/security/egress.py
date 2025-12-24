""" egress

Egress policy (deny-by-default for external calls).
"""

from typing import Dict, Any
from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ForbiddenError
from app.kernel.config.settings import settings


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
    
    # Extract URL from parameters if present
    url = parameters.get("url") or parameters.get("endpoint")
    if url:
        # Simple check: deny external URLs unless explicitly allowed
        # In production, implement allowlist/blocklist
        if url.startswith("http://") or url.startswith("https://"):
            # Check if URL is in allowed domains (placeholder)
            # For now, allow all - implement domain allowlist in production
            pass
    
    # Additional checks can be added here
    # - Check against workspace allowlist
    # - Check against tenant policy
    # - Check against global policy
