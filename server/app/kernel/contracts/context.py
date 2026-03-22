""" context

RequestContext and identity/scope primitives.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RequestContext:
    """Request context containing tenant, workspace, and user information.
    
    This context is resolved from JWT token/session and request headers/path.
    All workspace-scoped operations must include this context.
    """
    
    tenant_id: str
    """Tenant ID (required)."""
    
    workspace_id: str
    """Workspace ID (required for workspace-scoped operations)."""
    
    user_id: str
    """User ID (required)."""

    request_id: Optional[str] = None
    """Request ID for tracing (optional)."""

    trace_id: Optional[str] = None
    """Trace ID for correlation (optional)."""
    
    tenant_role: Optional[str] = None
    """User's role in tenant (Owner/Admin/Dev/Viewer)."""
    
    workspace_role: Optional[str] = None
    """User's role in workspace (Owner/Admin/Dev/Viewer)."""

    llm_rate_limit_per_minute: Optional[int] = None
    """Optional LLM rate limit (requests per minute)."""

    tool_rate_limit_per_minute: Optional[int] = None
    """Optional tool rate limit (requests per minute)."""

    llm_daily_quota: Optional[int] = None
    """Optional LLM daily request quota."""

    tool_daily_quota: Optional[int] = None
    """Optional tool daily request quota."""
    
    def is_tenant_admin(self) -> bool:
        """Check if user is tenant admin or owner.
        
        Returns:
            True if user has tenant admin/owner role.
        """
        return self.tenant_role in ("Owner", "Admin")

    def is_workspace_admin(self) -> bool:
        """Check if user is workspace admin.

        Returns:
            True if user is workspace admin.
        """
        return self.workspace_role == "Admin"
    
    def is_workspace_owner(self) -> bool:
        """Check if user is workspace owner.
        
        Returns:
            True if user is workspace owner.
        """
        return self.workspace_role == "Owner"
    
    def is_workspace_dev(self) -> bool:
        """Check if user is workspace dev (write-level) or higher.

        Returns:
            True if user has workspace dev/admin/owner role.
        """
        return self.workspace_role in ("Owner", "Admin", "Dev")

    def is_workspace_viewer(self) -> bool:
        """Check if user has workspace read access.

        Returns:
            True if user has any workspace role.
        """
        return self.workspace_role in ("Owner", "Admin", "Dev", "Viewer")
    
    def can_write(self) -> bool:
        """Check if user can write to workspace.
        
        Returns:
            True if user can write (Owner/Admin/Dev).
        """
        return self.is_workspace_dev()
    
    def can_read(self) -> bool:
        """Check if user can read from workspace.
        
        Returns:
            True if user can read (any role).
        """
        return self.is_workspace_viewer()
