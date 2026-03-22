""" scope

Scope checking utilities.
"""

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ForbiddenError
from app.kernel.identity.rbac import check_tenant_access, check_workspace_access


def verify_tenant_scope(ctx: RequestContext, target_tenant_id: str) -> None:
    """Verify tenant scope.
    
    Args:
        ctx: Request context.
        target_tenant_id: Target tenant ID.
        
    Raises:
        ForbiddenError: If scope mismatch.
    """
    check_tenant_access(ctx, target_tenant_id)


def verify_workspace_scope(ctx: RequestContext, target_workspace_id: str) -> None:
    """Verify workspace scope.
    
    Args:
        ctx: Request context.
        target_workspace_id: Target workspace ID.
        
    Raises:
        ForbiddenError: If scope mismatch.
    """
    check_workspace_access(ctx, target_workspace_id)

