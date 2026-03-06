"""permissions

Shared RBAC dependencies for API routes.
"""

from fastapi import Depends

from app.kernel.contracts.context import RequestContext
from app.kernel.identity.rbac import (
    require_workspace_read_async,
    require_workspace_write_async,
    require_workspace_owner_async,
    require_tenant_admin_async,
)
from app.middleware.auth import get_current_context


async def require_workspace_read_ctx(
    ctx: RequestContext = Depends(get_current_context),
) -> RequestContext:
    """Require workspace read access."""
    await require_workspace_read_async(ctx)
    return ctx


async def require_workspace_write_ctx(
    ctx: RequestContext = Depends(get_current_context),
) -> RequestContext:
    """Require workspace write access."""
    await require_workspace_write_async(ctx)
    return ctx


async def require_workspace_owner_ctx(
    ctx: RequestContext = Depends(get_current_context),
) -> RequestContext:
    """Require workspace owner access."""
    await require_workspace_owner_async(ctx)
    return ctx


async def require_tenant_admin_ctx(
    ctx: RequestContext = Depends(get_current_context),
) -> RequestContext:
    """Require tenant admin access."""
    await require_tenant_admin_async(ctx)
    return ctx
