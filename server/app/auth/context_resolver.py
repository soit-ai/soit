""" context_resolver

Resolve RequestContext from request + membership.
"""

import hashlib
from datetime import UTC, timedelta

from fastapi import Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import client_address as addresses
from app.kernel.commons.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.api_key_scopes import normalize_scopes
from app.kernel.identity.auth import JWTManager
from app.kernel.identity.rbac import lower_workspace_role
from app.kernel.identity.workspace_access import WorkspaceAccessResolver
from app.kernel.runtime.runs.content_capture import stricter_capture
from app.settings.settings import settings

security = HTTPBearer()

API_KEY_PREFIX = "sk_"
"""Prefix every issued API key starts with."""

LAST_USED_WRITE_INTERVAL = timedelta(minutes=1)


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
            return await self.resolve_from_api_key(
                api_key,
                workspace_id_header,
                client_address=addresses.client_address(request, settings.trusted_proxies),
            )

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

        # OpenAI SDKs and most HTTP clients send an API key as a bearer token.
        # A signed session token never carries the key prefix, so the two
        # cannot be confused.
        if token.startswith(API_KEY_PREFIX):
            return await self.resolve_from_api_key(
                token,
                workspace_id_header,
                client_address=addresses.client_address(request, settings.trusted_proxies),
            )

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

        access = await self.workspace_access_resolver.resolve(
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
            content_capture=access.content_capture,
        )

    async def resolve_from_api_key(
        self,
        api_key: str,
        workspace_id_header: str | None = None,
        *,
        client_address: str | None = None,
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
        from app.infra.db.session import get_async_session_local
        from app.modules.identity.domain.models import ServicePrincipal
        from app.modules.identity.infra.repository import (
            ApiKeyRepository,
            TenantMembershipRepository,
        )

        db = get_async_session_local()()
        try:
            api_repo = ApiKeyRepository(db)
            key = await api_repo.get_by_hash(key_hash)
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
            allowlist = key.ip_allowlist_json
            if allowlist is not None and not addresses.address_allowed(client_address, allowlist):
                # The address is not echoed back: a caller probing the list
                # learns nothing about which ranges it holds.
                raise ForbiddenError(
                    "API key is not accepted from this address",
                    {"reason": "ip_not_allowed"},
                )
            scopes = normalize_scopes(key.scopes_json)
            if not scopes:
                # A key with no usable scope must not fall back to the owner's
                # role; that is exactly the inheritance this replaces.
                raise ForbiddenError("API key has no usable scope")

            subject_user_id = key.user_id
            principal_kind: str | None = None
            if key.principal_id is not None:
                # A key issued to a service principal acts as the principal, in
                # its own workspace only, with the lower of its role and its
                # owner's: the owner's standing bounds what it can do.
                principal = await db.get(ServicePrincipal, key.principal_id)
                if (
                    principal is None
                    or principal.status != "active"
                    or principal.tenant_id != key.tenant_id
                    or principal.workspace_id != key.workspace_id
                ):
                    raise UnauthorizedError("API key's service principal is not active")
                if workspace_id_header and workspace_id_header != principal.workspace_id:
                    raise ForbiddenError("A service principal acts only in its own workspace")
                target_workspace_id = principal.workspace_id
                access = await self.workspace_access_resolver.resolve(
                    key.tenant_id,
                    target_workspace_id,
                    principal.owner_user_id,
                )
                if access is None:
                    raise ForbiddenError(
                        "The service principal's owner is no longer a member of the workspace"
                    )
                workspace_role = lower_workspace_role(
                    principal.workspace_role, access.workspace_role
                )
                subject_user_id = principal.id
                principal_kind = "service_principal"
            else:
                target_workspace_id = workspace_id_header or key.workspace_id
                access = await self.workspace_access_resolver.resolve(
                    key.tenant_id,
                    target_workspace_id,
                    key.user_id,
                )
                if access is None:
                    raise ForbiddenError("User is not a member of the requested workspace")
                workspace_role = access.workspace_role

            now = utc_now()
            last_used_at = key.last_used_at
            if last_used_at is not None and last_used_at.tzinfo is None:
                last_used_at = last_used_at.replace(tzinfo=UTC)
            # A key in active use would otherwise write its row on every call;
            # "last used" needs minute precision, not request precision.
            if last_used_at is None or now - last_used_at >= LAST_USED_WRITE_INTERVAL:
                key.last_used_at = now
                key.updated_at = now
                await api_repo.update(key)

            tenant_role = None
            if principal_kind is None:
                # A service principal holds no tenant role.
                membership_repo = TenantMembershipRepository(db)
                tenant_membership = await membership_repo.get(key.tenant_id, key.user_id)
                if tenant_membership:
                    tenant_role = tenant_membership.role

            return RequestContext(
                tenant_id=key.tenant_id,
                workspace_id=target_workspace_id,
                user_id=subject_user_id,
                principal_kind=principal_kind,
                tenant_role=tenant_role,
                workspace_role=workspace_role,
                scopes=scopes,
                llm_rate_limit_per_minute=access.llm_rate_limit_per_minute,
                tool_rate_limit_per_minute=access.tool_rate_limit_per_minute,
                llm_daily_quota=access.llm_daily_quota,
                tool_daily_quota=access.tool_daily_quota,
                api_key_id=key.id,
                content_capture=stricter_capture(access.content_capture, key.content_capture),
                api_key_rate_limit_per_minute=key.rate_limit_per_minute,
                api_key_daily_request_quota=key.daily_request_quota,
                api_key_daily_token_quota=key.daily_token_quota,
                allowed_models=(
                    frozenset(key.allowed_models_json)
                    if key.allowed_models_json is not None
                    else None
                ),
                allowed_tools=(
                    frozenset(key.allowed_tools_json)
                    if key.allowed_tools_json is not None
                    else None
                ),
            )
        finally:
            await db.close()

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

        access = await self.workspace_access_resolver.resolve(
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
            content_capture=access.content_capture,
        )
