""" context_resolver

Resolve RequestContext from request + membership.
"""

import hashlib
from datetime import UTC

from fastapi import Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.kernel.commons.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.api_key_scopes import normalize_scopes
from app.kernel.identity.auth import JWTManager
from app.kernel.identity.workspace_access import WorkspaceAccessResolver

security = HTTPBearer()


class ContextResolver:
    """Resolve RequestContext from FastAPI request."""

    def __init__(
        self,
        jwt_manager: JWTManager,
        workspace_access_resolver: WorkspaceAccessResolver,
    ):
        """Initialize context resolver.

        Args:
            jwt_manager: JWT manager instance.
        """
        self.jwt_manager = jwt_manager
        self.workspace_access_resolver = workspace_access_resolver

    async def resolve_from_request(
        self,
        request: Request,
        workspace_id_header: str | None = Header(None, alias="X-Workspace-Id"),
        authorization: HTTPAuthorizationCredentials | None = None,
        api_key: str | None = None,
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
            return self.resolve_from_api_key(api_key, workspace_id_header)

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

        if not user_id or not tenant_id:
            raise UnauthorizedError("Token missing required claims")

        # A token minted for one step of sign-in authorizes nothing. Without
        # this, presenting the challenge token as a bearer would make the
        # second factor optional for anyone who noticed.
        if payload.get("purpose"):
            raise UnauthorizedError("Token cannot be used to authorize a request")

        # Resolve workspace ID
        workspace_id = workspace_id_header
        if not workspace_id:
            workspace_id = self._extract_workspace_from_path(request.url.path)
        if not workspace_id:
            workspace_id = payload.get("workspace_id")

        if not workspace_id:
            raise NotFoundError("Workspace ID required but not provided")

        access = self.workspace_access_resolver.resolve(
            str(tenant_id),
            str(workspace_id),
            str(user_id),
            session_id=payload.get("sid"),
        )
        if access is None:
            raise ForbiddenError("User is not a member of the requested workspace")

        return RequestContext(
            tenant_id=str(tenant_id),
            workspace_id=str(workspace_id),
            user_id=str(user_id),
            tenant_role=access.tenant_role,
            workspace_role=access.workspace_role,
            llm_rate_limit_per_minute=access.llm_rate_limit_per_minute,
            tool_rate_limit_per_minute=access.tool_rate_limit_per_minute,
            llm_daily_quota=access.llm_daily_quota,
            tool_daily_quota=access.tool_daily_quota,
        )

    def resolve_from_api_key(
        self,
        api_key: str,
        workspace_id_header: str | None = None,
    ) -> RequestContext:
        """Resolve RequestContext from API key.

        The workspace defaults to the one bound at key creation. An
        X-Workspace-Id header may target another workspace of the same
        tenant; the authoritative membership check below gates the switch,
        mirroring the JWT path.
        """
        if not api_key:
            raise UnauthorizedError("Missing API key")

        key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        from app.infra.db.session import get_db_sync
        from app.modules.identity.infra.repository import (
            ApiKeyRepository,
            TenantMembershipRepository,
        )

        db = get_db_sync()
        try:
            api_repo = ApiKeyRepository(db)
            key = api_repo.get_by_hash(key_hash)
            if not key or key.status != "active":
                raise UnauthorizedError("Invalid or revoked API key")
            expires_at = key.expires_at
            if expires_at is not None:
                # Not every backend returns an aware datetime for a timestamptz
                # column; expiries are stored in UTC, so read a naive value as
                # UTC rather than letting the comparison raise.
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
                if expires_at <= utc_now():
                    raise UnauthorizedError("API key has expired")
            scopes = normalize_scopes(key.scopes_json)
            if not scopes:
                # A key with no usable scope must not fall back to the owner's
                # role; that is exactly the inheritance this replaces.
                raise ForbiddenError("API key has no usable scope")

            target_workspace_id = workspace_id_header or key.workspace_id
            access = self.workspace_access_resolver.resolve(
                key.tenant_id,
                target_workspace_id,
                key.user_id,
            )
            if access is None:
                raise ForbiddenError("User is not a member of the requested workspace")

            key.last_used_at = utc_now()
            key.updated_at = utc_now()
            api_repo.update(key)

            tenant_role = None
            membership_repo = TenantMembershipRepository(db)
            tenant_membership = membership_repo.get(key.tenant_id, key.user_id)
            if tenant_membership:
                tenant_role = tenant_membership.role

            return RequestContext(
                tenant_id=key.tenant_id,
                workspace_id=target_workspace_id,
                user_id=key.user_id,
                tenant_role=tenant_role,
                workspace_role=access.workspace_role,
                scopes=scopes,
                llm_rate_limit_per_minute=access.llm_rate_limit_per_minute,
                tool_rate_limit_per_minute=access.tool_rate_limit_per_minute,
                llm_daily_quota=access.llm_daily_quota,
                tool_daily_quota=access.tool_daily_quota,
            )
        finally:
            db.close()

    def _extract_workspace_from_path(self, path: str) -> str | None:
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
        workspace_id: str | None = None,
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

        if not user_id or not tenant_id:
            raise UnauthorizedError("Token missing required claims")

        # A token minted for one step of sign-in authorizes nothing. Without
        # this, presenting the challenge token as a bearer would make the
        # second factor optional for anyone who noticed.
        if payload.get("purpose"):
            raise UnauthorizedError("Token cannot be used to authorize a request")

        # Use workspace_id from parameter or token
        resolved_workspace_id = workspace_id or payload.get("workspace_id")
        if not resolved_workspace_id:
            raise NotFoundError("Workspace ID required")

        access = self.workspace_access_resolver.resolve(
            str(tenant_id),
            str(resolved_workspace_id),
            str(user_id),
            session_id=payload.get("sid"),
        )
        if access is None:
            raise ForbiddenError("User is not a member of the requested workspace")

        return RequestContext(
            tenant_id=str(tenant_id),
            workspace_id=str(resolved_workspace_id),
            user_id=str(user_id),
            tenant_role=access.tenant_role,
            workspace_role=access.workspace_role,
            llm_rate_limit_per_minute=access.llm_rate_limit_per_minute,
            tool_rate_limit_per_minute=access.tool_rate_limit_per_minute,
            llm_daily_quota=access.llm_daily_quota,
            tool_daily_quota=access.tool_daily_quota,
        )
