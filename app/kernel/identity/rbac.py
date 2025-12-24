""" rbac

Core RBAC definitions and permission checks.
"""

from typing import Optional

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ForbiddenError


# Tenant roles
TENANT_ROLE_OWNER = "Owner"
TENANT_ROLE_ADMIN = "Admin"
TENANT_ROLE_MEMBER = "Member"

# Workspace roles
WORKSPACE_ROLE_OWNER = "Owner"
WORKSPACE_ROLE_MAINTAINER = "Maintainer"
WORKSPACE_ROLE_READER = "Reader"


def require_tenant_admin(ctx: RequestContext) -> None:
    """Require tenant admin or owner role.
    
    Args:
        ctx: Request context.
        
    Raises:
        ForbiddenError: If user is not tenant admin.
    """
    if not ctx.is_tenant_admin():
        raise ForbiddenError("Tenant admin role required")


def require_workspace_owner(ctx: RequestContext) -> None:
    """Require workspace owner role.
    
    Args:
        ctx: Request context.
        
    Raises:
        ForbiddenError: If user is not workspace owner.
    """
    if not ctx.is_workspace_owner():
        raise ForbiddenError("Workspace owner role required")


def require_workspace_write(ctx: RequestContext) -> None:
    """Require workspace write permission (Owner or Maintainer).
    
    Args:
        ctx: Request context.
        
    Raises:
        ForbiddenError: If user cannot write to workspace.
    """
    if not ctx.can_write():
        raise ForbiddenError("Workspace write permission required")


def require_workspace_read(ctx: RequestContext) -> None:
    """Require workspace read permission.
    
    Args:
        ctx: Request context.
        
    Raises:
        ForbiddenError: If user cannot read from workspace.
    """
    if not ctx.can_read():
        raise ForbiddenError("Workspace read permission required")


def check_tenant_access(ctx: RequestContext, target_tenant_id: str) -> None:
    """Check if user has access to target tenant.
    
    Args:
        ctx: Request context.
        target_tenant_id: Target tenant ID.
        
    Raises:
        ForbiddenError: If user cannot access target tenant.
    """
    if ctx.tenant_id != target_tenant_id:
        raise ForbiddenError("Access denied: different tenant")


def check_workspace_access(ctx: RequestContext, target_workspace_id: str) -> None:
    """Check if user has access to target workspace.
    
    Args:
        ctx: Request context.
        target_workspace_id: Target workspace ID.
        
    Raises:
        ForbiddenError: If user cannot access target workspace.
    """
    if ctx.workspace_id != target_workspace_id:
        raise ForbiddenError("Access denied: different workspace")
