""" context_resolver

Resolve RequestContext from request + membership.
"""

from typing import Optional
import hashlib

from fastapi import Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.kernel.contracts.context import RequestContext
from app.kernel.identity.auth import JWTManager
from app.kernel.commons.errors import UnauthorizedError, NotFoundError
from app.kernel.commons.time import utc_now


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
        api_key: Optional[str] = None,
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
        if api_key:
            return self.resolve_from_api_key(api_key)

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
            workspace_id = self._extract_workspace_from_path(request.url.path)
        if not workspace_id:
            workspace_id = payload.get("workspace_id")

        if not workspace_id:
            raise NotFoundError("Workspace ID required but not provided")
        
        # Get workspace role from token or resolve from membership
        workspace_role = payload.get("workspace_role")
        
        llm_rate_limit = None
        tool_rate_limit = None
        llm_daily_quota = None
        tool_daily_quota = None

        # Query database for membership and limits
        if workspace_id:
            from app.infra.db.session import get_db_sync
            from app.modules.identity.infra.repository import (
                WorkspaceMembershipRepository,
                TenantRepository,
                WorkspaceRepository,
            )
            from app.kernel.contracts.context import RequestContext as RC

            temp_ctx = RC(
                tenant_id=str(tenant_id),
                workspace_id=str(workspace_id),
                user_id=str(user_id),
                tenant_role=tenant_role,
            )

            db = get_db_sync()
            try:
                if not workspace_role:
                    membership_repo = WorkspaceMembershipRepository(db, temp_ctx)
                    membership = membership_repo.get(workspace_id, str(user_id))
                    if membership:
                        workspace_role = membership.role

                tenant_repo = TenantRepository(db)
                workspace_repo = WorkspaceRepository(db, temp_ctx)
                tenant = tenant_repo.get_by_id(str(tenant_id))
                workspace = workspace_repo.get_by_id(str(workspace_id))

                if tenant:
                    llm_rate_limit = tenant.llm_rate_limit_per_minute
                    tool_rate_limit = tenant.tool_rate_limit_per_minute
                    llm_daily_quota = tenant.llm_daily_quota
                    tool_daily_quota = tenant.tool_daily_quota

                if workspace:
                    if workspace.llm_rate_limit_per_minute is not None:
                        llm_rate_limit = workspace.llm_rate_limit_per_minute
                    if workspace.tool_rate_limit_per_minute is not None:
                        tool_rate_limit = workspace.tool_rate_limit_per_minute
                    if workspace.llm_daily_quota is not None:
                        llm_daily_quota = workspace.llm_daily_quota
                    if workspace.tool_daily_quota is not None:
                        tool_daily_quota = workspace.tool_daily_quota
            except Exception:
                pass
            finally:
                db.close()
        
        return RequestContext(
            tenant_id=str(tenant_id),
            workspace_id=str(workspace_id),
            user_id=str(user_id),
            tenant_role=tenant_role,
            workspace_role=workspace_role,
            llm_rate_limit_per_minute=llm_rate_limit,
            tool_rate_limit_per_minute=tool_rate_limit,
            llm_daily_quota=llm_daily_quota,
            tool_daily_quota=tool_daily_quota,
        )

    def resolve_from_api_key(
        self,
        api_key: str,
    ) -> RequestContext:
        """Resolve RequestContext from API key."""
        if not api_key:
            raise UnauthorizedError("Missing API key")

        key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        from app.infra.db.session import get_db_sync
        from app.modules.identity.infra.repository import (
            ApiKeyRepository,
            TenantMembershipRepository,
            WorkspaceMembershipRepository,
            TenantRepository,
            WorkspaceRepository,
        )
        from app.kernel.contracts.context import RequestContext as RC

        db = get_db_sync()
        try:
            api_repo = ApiKeyRepository(db)
            key = api_repo.get_by_hash(key_hash)
            if not key or key.status != "active":
                raise UnauthorizedError("Invalid or revoked API key")

            key.last_used_at = utc_now()
            key.updated_at = utc_now()
            api_repo.update(key)

            tenant_role = None
            membership_repo = TenantMembershipRepository(db)
            tenant_membership = membership_repo.get(key.tenant_id, key.user_id)
            if tenant_membership:
                tenant_role = tenant_membership.role

            temp_ctx = RC(
                tenant_id=key.tenant_id,
                workspace_id=key.workspace_id,
                user_id=key.user_id,
                tenant_role=tenant_role,
            )
            workspace_role = None
            workspace_membership_repo = WorkspaceMembershipRepository(db, temp_ctx)
            workspace_membership = workspace_membership_repo.get(key.workspace_id, key.user_id)
            if workspace_membership:
                workspace_role = workspace_membership.role

            tenant = TenantRepository(db).get_by_id(key.tenant_id)
            workspace = WorkspaceRepository(db, temp_ctx).get_by_id(key.workspace_id)

            llm_rate_limit = tenant.llm_rate_limit_per_minute if tenant else None
            tool_rate_limit = tenant.tool_rate_limit_per_minute if tenant else None
            llm_daily_quota = tenant.llm_daily_quota if tenant else None
            tool_daily_quota = tenant.tool_daily_quota if tenant else None

            if workspace:
                if workspace.llm_rate_limit_per_minute is not None:
                    llm_rate_limit = workspace.llm_rate_limit_per_minute
                if workspace.tool_rate_limit_per_minute is not None:
                    tool_rate_limit = workspace.tool_rate_limit_per_minute
                if workspace.llm_daily_quota is not None:
                    llm_daily_quota = workspace.llm_daily_quota
                if workspace.tool_daily_quota is not None:
                    tool_daily_quota = workspace.tool_daily_quota

            return RequestContext(
                tenant_id=key.tenant_id,
                workspace_id=key.workspace_id,
                user_id=key.user_id,
                tenant_role=tenant_role,
                workspace_role=workspace_role,
                llm_rate_limit_per_minute=llm_rate_limit,
                tool_rate_limit_per_minute=tool_rate_limit,
                llm_daily_quota=llm_daily_quota,
                tool_daily_quota=tool_daily_quota,
            )
        finally:
            db.close()
    
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
