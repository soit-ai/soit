""" rbac

Core RBAC definitions and permission checks.
"""

from typing import Optional
from enum import Enum

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ForbiddenError
from app.kernel.identity.permissions import (
    require_resource_read_async,
    require_resource_write_async,
    require_resource_delete_async,
    RESOURCE_AGENT,
    RESOURCE_WORKFLOW,
    RESOURCE_KNOWLEDGE,
    RESOURCE_MODEL,
    RESOURCE_PLUGIN,
    RESOURCE_MEMORY,
)


# Tenant roles
TENANT_ROLE_OWNER = "Owner"
TENANT_ROLE_ADMIN = "Admin"
TENANT_ROLE_DEV = "Dev"
TENANT_ROLE_VIEWER = "Viewer"

TENANT_ROLES = {
    TENANT_ROLE_OWNER,
    TENANT_ROLE_ADMIN,
    TENANT_ROLE_DEV,
    TENANT_ROLE_VIEWER,
}

# Workspace roles
WORKSPACE_ROLE_OWNER = "Owner"
WORKSPACE_ROLE_ADMIN = "Admin"
WORKSPACE_ROLE_DEV = "Dev"
WORKSPACE_ROLE_VIEWER = "Viewer"

WORKSPACE_ROLES = {
    WORKSPACE_ROLE_OWNER,
    WORKSPACE_ROLE_ADMIN,
    WORKSPACE_ROLE_DEV,
    WORKSPACE_ROLE_VIEWER,
}


class UserRole(str, Enum):
    """Tenant-level user roles."""

    OWNER = TENANT_ROLE_OWNER
    ADMIN = TENANT_ROLE_ADMIN
    DEV = TENANT_ROLE_DEV
    VIEWER = TENANT_ROLE_VIEWER


class WorkspaceRole(str, Enum):
    """Workspace-level user roles."""

    OWNER = WORKSPACE_ROLE_OWNER
    ADMIN = WORKSPACE_ROLE_ADMIN
    DEV = WORKSPACE_ROLE_DEV
    VIEWER = WORKSPACE_ROLE_VIEWER


def check_permission(ctx: RequestContext, resource_type: str, action: str) -> bool:
    """Check if the user has permission for a resource action."""
    normalized = action.strip().lower()
    if normalized in ("create", "update"):
        normalized = "write"
    if normalized == "run":
        normalized = "execute"

    if ctx.is_workspace_owner() or ctx.is_workspace_admin():
        return True
    if normalized == "delete":
        return False
    if normalized in ("write", "execute"):
        return ctx.is_workspace_dev()
    if normalized == "read":
        return ctx.can_read()
    return False


def require_tenant_admin(ctx: RequestContext) -> None:
    """Require tenant admin or owner role.
    
    Args:
        ctx: Request context.
        
    Raises:
        ForbiddenError: If user is not tenant admin.
    """
    if not ctx.is_tenant_admin():
        raise ForbiddenError("Tenant admin role required")


async def require_tenant_admin_async(ctx: RequestContext) -> None:
    """Require tenant admin or owner role (async)."""
    require_tenant_admin(ctx)


def require_workspace_owner(ctx: RequestContext) -> None:
    """Require workspace owner role.
    
    Args:
        ctx: Request context.
        
    Raises:
        ForbiddenError: If user is not workspace owner.
    """
    if not ctx.is_workspace_owner():
        raise ForbiddenError("Workspace owner role required")


async def require_workspace_owner_async(ctx: RequestContext) -> None:
    """Require workspace owner role (async)."""
    require_workspace_owner(ctx)


def require_workspace_write(ctx: RequestContext) -> None:
    """Require workspace write permission (Owner/Admin/Dev).
    
    Args:
        ctx: Request context.
        
    Raises:
        ForbiddenError: If user cannot write to workspace.
    """
    if not ctx.can_write():
        raise ForbiddenError("Workspace write permission required")


async def require_workspace_write_async(ctx: RequestContext) -> None:
    """Require workspace write permission (async)."""
    require_workspace_write(ctx)


def require_workspace_read(ctx: RequestContext) -> None:
    """Require workspace read permission.
    
    Args:
        ctx: Request context.
        
    Raises:
        ForbiddenError: If user cannot read from workspace.
    """
    if not ctx.can_read():
        raise ForbiddenError("Workspace read permission required")


async def require_workspace_read_async(ctx: RequestContext) -> None:
    """Require workspace read permission (async)."""
    require_workspace_read(ctx)


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
async def require_workflow_read(ctx: RequestContext, workflow_id: str, owner_id: Optional[str] = None) -> None:
    """Require read permission on workflow (async)."""
    await require_resource_read_async(ctx, RESOURCE_WORKFLOW, workflow_id, owner_id)


async def require_workflow_write(ctx: RequestContext, workflow_id: str, owner_id: Optional[str] = None) -> None:
    """Require write permission on workflow (async)."""
    await require_resource_write_async(ctx, RESOURCE_WORKFLOW, workflow_id, owner_id)


async def require_workflow_delete(ctx: RequestContext, workflow_id: str, owner_id: Optional[str] = None) -> None:
    """Require delete permission on workflow (async)."""
    await require_resource_delete_async(ctx, RESOURCE_WORKFLOW, workflow_id, owner_id)


async def require_knowledge_read(ctx: RequestContext, knowledge_id: str, owner_id: Optional[str] = None) -> None:
    """Require read permission on knowledge (async)."""
    await require_resource_read_async(ctx, RESOURCE_KNOWLEDGE, knowledge_id, owner_id)


async def require_knowledge_write(ctx: RequestContext, knowledge_id: str, owner_id: Optional[str] = None) -> None:
    """Require write permission on knowledge (async)."""
    await require_resource_write_async(ctx, RESOURCE_KNOWLEDGE, knowledge_id, owner_id)


async def require_knowledge_delete(ctx: RequestContext, knowledge_id: str, owner_id: Optional[str] = None) -> None:
    """Require delete permission on knowledge (async)."""
    await require_resource_delete_async(ctx, RESOURCE_KNOWLEDGE, knowledge_id, owner_id)


async def require_model_read(ctx: RequestContext, model_id: str, owner_id: Optional[str] = None) -> None:
    """Require read permission on model (async)."""
    await require_resource_read_async(ctx, RESOURCE_MODEL, model_id, owner_id)


async def require_model_write(ctx: RequestContext, model_id: str, owner_id: Optional[str] = None) -> None:
    """Require write permission on model (async)."""
    await require_resource_write_async(ctx, RESOURCE_MODEL, model_id, owner_id)


async def require_model_delete(ctx: RequestContext, model_id: str, owner_id: Optional[str] = None) -> None:
    """Require delete permission on model (async)."""
    await require_resource_delete_async(ctx, RESOURCE_MODEL, model_id, owner_id)


async def require_plugin_read(ctx: RequestContext, plugin_id: str, owner_id: Optional[str] = None) -> None:
    """Require read permission on plugin (async)."""
    await require_resource_read_async(ctx, RESOURCE_PLUGIN, plugin_id, owner_id)


async def require_plugin_write(ctx: RequestContext, plugin_id: str, owner_id: Optional[str] = None) -> None:
    """Require write permission on plugin (async)."""
    await require_resource_write_async(ctx, RESOURCE_PLUGIN, plugin_id, owner_id)


async def require_plugin_delete(ctx: RequestContext, plugin_id: str, owner_id: Optional[str] = None) -> None:
    """Require delete permission on plugin (async)."""
    await require_resource_delete_async(ctx, RESOURCE_PLUGIN, plugin_id, owner_id)


async def require_memory_read(ctx: RequestContext, memory_id: str, owner_id: Optional[str] = None) -> None:
    """Require read permission on memory (async)."""
    await require_resource_read_async(ctx, RESOURCE_MEMORY, memory_id, owner_id)


async def require_memory_write(ctx: RequestContext, memory_id: str, owner_id: Optional[str] = None) -> None:
    """Require write permission on memory (async)."""
    await require_resource_write_async(ctx, RESOURCE_MEMORY, memory_id, owner_id)


async def require_memory_delete(ctx: RequestContext, memory_id: str, owner_id: Optional[str] = None) -> None:
    """Require delete permission on memory (async)."""
    await require_resource_delete_async(ctx, RESOURCE_MEMORY, memory_id, owner_id)
