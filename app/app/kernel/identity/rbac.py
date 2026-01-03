""" rbac

Core RBAC definitions and permission checks.
"""

from typing import Optional

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ForbiddenError
from app.kernel.identity.permissions import (
    require_resource_read,
    require_resource_write,
    require_resource_delete,
    RESOURCE_WORKFLOW,
    RESOURCE_DATASET,
    RESOURCE_MODEL,
    RESOURCE_PLUGIN,
    RESOURCE_APP,
)


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


# Resource-level permission helpers
def require_workflow_read(ctx: RequestContext, workflow_id: str, owner_id: Optional[str] = None) -> None:
    """Require read permission on workflow."""
    require_resource_read(ctx, RESOURCE_WORKFLOW, workflow_id, owner_id)


def require_workflow_write(ctx: RequestContext, workflow_id: str, owner_id: Optional[str] = None) -> None:
    """Require write permission on workflow."""
    require_resource_write(ctx, RESOURCE_WORKFLOW, workflow_id, owner_id)


def require_workflow_delete(ctx: RequestContext, workflow_id: str, owner_id: Optional[str] = None) -> None:
    """Require delete permission on workflow."""
    require_resource_delete(ctx, RESOURCE_WORKFLOW, workflow_id, owner_id)


def require_dataset_read(ctx: RequestContext, dataset_id: str, owner_id: Optional[str] = None) -> None:
    """Require read permission on dataset."""
    require_resource_read(ctx, RESOURCE_DATASET, dataset_id, owner_id)


def require_dataset_write(ctx: RequestContext, dataset_id: str, owner_id: Optional[str] = None) -> None:
    """Require write permission on dataset."""
    require_resource_write(ctx, RESOURCE_DATASET, dataset_id, owner_id)


def require_dataset_delete(ctx: RequestContext, dataset_id: str, owner_id: Optional[str] = None) -> None:
    """Require delete permission on dataset."""
    require_resource_delete(ctx, RESOURCE_DATASET, dataset_id, owner_id)


def require_model_read(ctx: RequestContext, model_id: str, owner_id: Optional[str] = None) -> None:
    """Require read permission on model."""
    require_resource_read(ctx, RESOURCE_MODEL, model_id, owner_id)


def require_model_write(ctx: RequestContext, model_id: str, owner_id: Optional[str] = None) -> None:
    """Require write permission on model."""
    require_resource_write(ctx, RESOURCE_MODEL, model_id, owner_id)


def require_model_delete(ctx: RequestContext, model_id: str, owner_id: Optional[str] = None) -> None:
    """Require delete permission on model."""
    require_resource_delete(ctx, RESOURCE_MODEL, model_id, owner_id)
