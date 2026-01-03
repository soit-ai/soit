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
    
    tenant_role: Optional[str] = None
    """User's role in tenant (Owner/Admin/Member)."""
    
    workspace_role: Optional[str] = None
    """User's role in workspace (Owner/Maintainer/Reader)."""
    
    def is_tenant_admin(self) -> bool:
        """Check if user is tenant admin or owner.
        
        Returns:
            True if user has tenant admin/owner role.
        """
        return self.tenant_role in ("Owner", "Admin")
    
    def is_workspace_owner(self) -> bool:
        """Check if user is workspace owner.
        
        Returns:
            True if user is workspace owner.
        """
        return self.workspace_role == "Owner"
    
    def is_workspace_maintainer(self) -> bool:
        """Check if user is workspace maintainer or owner.
        
        Returns:
            True if user has workspace maintainer/owner role.
        """
        return self.workspace_role in ("Owner", "Maintainer")
    
    def can_write(self) -> bool:
        """Check if user can write to workspace.
        
        Returns:
            True if user can write (Owner or Maintainer).
        """
        return self.is_workspace_maintainer()
    
    def can_read(self) -> bool:
        """Check if user can read from workspace.
        
        Returns:
            True if user can read (any role).
        """
        return self.workspace_role is not None
