""" auth

Authentication middleware for FastAPI.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth.context_resolver import ContextResolver
from app.kernel.contracts.context import RequestContext
from app.settings.settings import settings
from app.kernel.observability.context import set_request_context
from app.kernel.identity.auth import decode_jwt_token


security = HTTPBearer(auto_error=False)


# Global context resolver instance
_context_resolver: Optional[ContextResolver] = None


def get_context_resolver() -> ContextResolver:
    """Get or create context resolver instance.
    
    Returns:
        ContextResolver instance.
    """
    global _context_resolver
    if _context_resolver is None:
        # Create a simple resolver that uses decode_jwt_token
        class SimpleJWTManager:
            def decode_token(self, token: str):
                return decode_jwt_token(token)
        
        jwt_manager = SimpleJWTManager()
        _context_resolver = ContextResolver(jwt_manager)
    return _context_resolver


async def get_current_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> RequestContext:
    """Dependency to get current request context.
    
    Args:
        request: FastAPI request object.
        credentials: HTTP authorization credentials.
        x_workspace_id: Workspace ID from header.
        
    Returns:
        RequestContext instance.
        
    Raises:
        HTTPException: If authentication fails.
    """
    try:
        resolver = get_context_resolver()
        context = await resolver.resolve_from_request(
            request,
            workspace_id_header=x_workspace_id,
            authorization=credentials,
            api_key=x_api_key,
        )
        request_id = getattr(request.state, "request_id", None)
        trace_id = getattr(request.state, "trace_id", None)
        if request_id or trace_id:
            context = RequestContext(
                tenant_id=context.tenant_id,
                workspace_id=context.workspace_id,
                user_id=context.user_id,
                request_id=request_id,
                trace_id=trace_id,
                tenant_role=context.tenant_role,
                workspace_role=context.workspace_role,
                llm_rate_limit_per_minute=context.llm_rate_limit_per_minute,
                tool_rate_limit_per_minute=context.tool_rate_limit_per_minute,
                llm_daily_quota=context.llm_daily_quota,
                tool_daily_quota=context.tool_daily_quota,
            )
        set_request_context(
            request_id=request_id,
            trace_id=trace_id,
            tenant_id=context.tenant_id,
            workspace_id=context.workspace_id,
            user_id=context.user_id,
        )
        return context
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
        )


async def get_current_context_from_request(
    request: Request,
    workspace_id_header: Optional[str] = None,
) -> RequestContext:
    """Get current context from FastAPI request.
    
    Args:
        request: FastAPI request object.
        workspace_id_header: Optional workspace ID from header.
        
    Returns:
        RequestContext instance.
        
    Raises:
        HTTPException: If authentication fails.
    """
    try:
        resolver = get_context_resolver()
        context = await resolver.resolve_from_request(
            request,
            workspace_id_header=workspace_id_header,
        )
        request_id = getattr(request.state, "request_id", None)
        trace_id = getattr(request.state, "trace_id", None)
        if request_id or trace_id:
            context = RequestContext(
                tenant_id=context.tenant_id,
                workspace_id=context.workspace_id,
                user_id=context.user_id,
                request_id=request_id,
                trace_id=trace_id,
                tenant_role=context.tenant_role,
                workspace_role=context.workspace_role,
                llm_rate_limit_per_minute=context.llm_rate_limit_per_minute,
                tool_rate_limit_per_minute=context.tool_rate_limit_per_minute,
                llm_daily_quota=context.llm_daily_quota,
                tool_daily_quota=context.tool_daily_quota,
            )
        set_request_context(
            request_id=request_id,
            trace_id=trace_id,
            tenant_id=context.tenant_id,
            workspace_id=context.workspace_id,
            user_id=context.user_id,
        )
        return context
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
        )
