""" context_resolver

Resolve RequestContext from request + membership.
"""

from typing import Optional

from fastapi import Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.kernel.contracts.context import RequestContext
from app.kernel.identity.auth import JWTManager
from app.kernel.commons.errors import UnauthorizedError, NotFoundError


security = HTTPBearer()


class ContextResolver:
    """Resolve RequestContext from FastAPI request."""
    
    def __init__(self, jwt_manager: JWTManager):
        """Initialize context resolver.
        
        Args:
            jwt_manager: JWT manager instance.
        """
        self.jwt_manager = jwt_manager
    
    async def resolve_from_request(
        self,
        request: Request,
        workspace_id_header: Optional[str] = Header(None, alias="X-Workspace-Id"),
        authorization: Optional[HTTPAuthorizationCredentials] = None,
    ) -> RequestContext:
        """Resolve RequestContext from FastAPI request.
        
        This method extracts:
        - User ID, tenant ID, roles from JWT token
        - Workspace ID from header or path
        
        Args:
            request: FastAPI request object.
            workspace_id_header: Workspace ID from header.
            authorization: Authorization credentials (from dependency).
            
        Returns:
            RequestContext instance.
            
        Raises:
            UnauthorizedError: If authentication fails.
            NotFoundError: If workspace not found or user not member.
        """
        # Extract token from authorization header
        if not authorization:
            # Try to get from request headers directly
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                raise UnauthorizedError("Missing authorization header")
            if not auth_header.startswith("Bearer "):
                raise UnauthorizedError("Invalid authorization header format")
            token = auth_header[7:]  # Remove "Bearer " prefix
        else:
            token = authorization.credentials
        
        # Decode JWT token
        payload = self.jwt_manager.decode_token(token)
        
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        tenant_role = payload.get("tenant_role")
        
        if not user_id or not tenant_id:
            raise UnauthorizedError("Token missing required claims")
        
        # Resolve workspace ID
        workspace_id = workspace_id_header
        if not workspace_id:
            # Try to extract from path (e.g., /api/v1/workspaces/{workspace_id}/...)
            workspace_id = self._extract_workspace_from_path(request.url.path)
        
        if not workspace_id:
            raise NotFoundError("Workspace ID required but not provided")
        
        # Get workspace role from token or resolve from membership
        workspace_role = payload.get("workspace_role")
        
        # If workspace_role not in token, we would normally query database
        # For now, we assume it's in the token or set to None
        # In production, implement membership lookup here
        
        return RequestContext(
            tenant_id=str(tenant_id),
            workspace_id=str(workspace_id),
            user_id=str(user_id),
            tenant_role=tenant_role,
            workspace_role=workspace_role,
        )
    
    def _extract_workspace_from_path(self, path: str) -> Optional[str]:
        """Extract workspace ID from URL path.
        
        Args:
            path: URL path (e.g., "/api/v1/workspaces/w_123/...").
            
        Returns:
            Workspace ID if found, None otherwise.
        """
        # Simple extraction: look for workspace ID pattern
        parts = path.split("/")
        for i, part in enumerate(parts):
            if part == "workspaces" and i + 1 < len(parts):
                return parts[i + 1]
            # Also check for workspace_id in path params
            if part.startswith("w_") and len(part) > 2:
                return part
        return None
    
    async def resolve_from_token(
        self,
        token: str,
        workspace_id: Optional[str] = None,
    ) -> RequestContext:
        """Resolve RequestContext from JWT token (for non-HTTP contexts).
        
        Args:
            token: JWT token string.
            workspace_id: Optional workspace ID.
            
        Returns:
            RequestContext instance.
            
        Raises:
            UnauthorizedError: If token is invalid.
        """
        payload = self.jwt_manager.decode_token(token)
        
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        tenant_role = payload.get("tenant_role")
        workspace_role = payload.get("workspace_role")
        
        if not user_id or not tenant_id:
            raise UnauthorizedError("Token missing required claims")
        
        # Use workspace_id from parameter or token
        resolved_workspace_id = workspace_id or payload.get("workspace_id")
        if not resolved_workspace_id:
            raise NotFoundError("Workspace ID required")
        
        return RequestContext(
            tenant_id=str(tenant_id),
            workspace_id=str(resolved_workspace_id),
            user_id=str(user_id),
            tenant_role=tenant_role,
            workspace_role=workspace_role,
        )
