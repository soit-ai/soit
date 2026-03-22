""" rbac

RBAC security checks (re-export from identity.rbac for convenience).
"""

from app.kernel.identity.rbac import (
    require_tenant_admin,
    require_workspace_owner,
    require_workspace_write,
    require_workspace_read,
    check_tenant_access,
    check_workspace_access,
)

__all__ = [
    "require_tenant_admin",
    "require_workspace_owner",
    "require_workspace_write",
    "require_workspace_read",
    "check_tenant_access",
    "check_workspace_access",
]

