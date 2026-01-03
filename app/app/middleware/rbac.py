""" rbac

RBAC authorization middleware and decorators.
"""

from functools import wraps
from typing import Callable, Optional
from fastapi import HTTPException, status, Depends

from app.kernel.contracts.context import RequestContext
from app.kernel.identity.rbac import UserRole, WorkspaceRole, check_permission
from app.middleware.auth import get_current_context


def require_user_role(role: UserRole):
    """Decorator to require a specific user role.
    
    Args:
        role: Required user role.
        
    Returns:
        Decorator function.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ctx: RequestContext = kwargs.get("ctx")
            if not ctx:
                # Try to get from dependencies
                ctx = kwargs.get("current_context")
            
            if not ctx:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )
            
            # Check role
            if not hasattr(ctx, "tenant_role") or ctx.tenant_role != role.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires {role.value} role",
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_workspace_role(role: WorkspaceRole):
    """Decorator to require a specific workspace role.
    
    Args:
        role: Required workspace role.
        
    Returns:
        Decorator function.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            ctx: RequestContext = kwargs.get("ctx")
            if not ctx:
                ctx = kwargs.get("current_context")
            
            if not ctx:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )
            
            # Check workspace role
            if not hasattr(ctx, "workspace_role") or ctx.workspace_role != role.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires workspace {role.value} role",
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_permission(resource_type: str, action: str):
    """Dependency to require a specific permission.
    
    Args:
        resource_type: Resource type (e.g., "workflow", "dataset").
        action: Action (e.g., "create", "read", "update", "delete").
        
    Returns:
        Dependency function.
    """
    async def permission_checker(
        ctx: RequestContext = Depends(get_current_context),
    ) -> RequestContext:
        """Check permission and return context."""
        if not check_permission(ctx, resource_type, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {action} on {resource_type}",
            )
        return ctx
    
    return permission_checker

