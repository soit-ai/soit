""" auth

Authentication middleware for FastAPI.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.kernel.identity.context_resolver import ContextResolver
from app.kernel.contracts.context import RequestContext
from app.kernel.config.settings import settings
from app.kernel.identity.auth import decode_jwt_token


security = HTTPBearer()


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
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
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
        return context
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
        )

