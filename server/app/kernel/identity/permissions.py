""" permissions

Resource-level permission checks and caching.
"""

import os
from typing import Protocol

import redis.asyncio as redis_async

from app.kernel.commons.errors import ForbiddenError
from app.kernel.contracts.context import RequestContext
from app.settings.settings import settings

# Resource types
RESOURCE_AGENT = "agent"
RESOURCE_WORKFLOW = "workflow"
RESOURCE_KNOWLEDGE = "knowledge"
RESOURCE_MODEL = "model"
RESOURCE_PLUGIN = "plugin"
RESOURCE_MEMORY = "memory"

# Actions
ACTION_READ = "read"
ACTION_WRITE = "write"
ACTION_DELETE = "delete"
ACTION_EXECUTE = "execute"
ACTION_PUBLISH = "publish"
ACTION_CREATE = "create"
ACTION_UPDATE = "update"
ACTION_RUN = "run"
ACTION_EXECUTE_ALIAS = "execute"
PERMISSION_CACHE_VERSION = "v3"


class ResourceGrantProvider(Protocol):
    """Provider boundary for resource grant lookup."""

    def allows_resource_action(
        self,
        *,
        ctx: RequestContext,
        resource_type: str,
        resource_id: str,
        action: str,
        effective_action: str,
    ) -> bool:
        """Return True when an explicit grant allows this action."""


_resource_grant_provider: ResourceGrantProvider | None = None


def register_resource_grant_provider(provider: ResourceGrantProvider) -> None:
    """Register the process-wide resource grant provider."""

    global _resource_grant_provider
    _resource_grant_provider = provider


def reset_resource_grant_provider() -> None:
    """Clear the process-wide resource grant provider."""

    global _resource_grant_provider
    _resource_grant_provider = None


def get_resource_grant_provider() -> ResourceGrantProvider | None:
    """Return the registered resource grant provider, if any."""

    return _resource_grant_provider


def _resource_type_aliases(resource_type: str) -> tuple[str, ...]:
    normalized = (resource_type or "").strip().lower()
    return (normalized,)


class PermissionCache:
    """Permission cache using Redis."""

    def __init__(self, redis_client: redis_async.Redis | None = None):
        """Initialize permission cache.

        Args:
            redis_client: Optional Redis client.
        """
        self._redis: redis_async.Redis | None = redis_client
        self._redis_pool: redis_async.ConnectionPool | None = None
        self._cache_ttl = 300  # 5 minutes

    async def _get_redis(self) -> redis_async.Redis | None:
        """Get or create Redis client.

        Returns:
            Redis client instance or None if Redis unavailable.
        """
        if self._redis is not None:
            return self._redis
        if os.getenv("PYTEST_CURRENT_TEST"):
            return None
        if not settings.redis_url or "None" in settings.redis_url:
            return None

        try:
            if self._redis_pool is None:
                self._redis_pool = redis_async.ConnectionPool.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=1,
                    socket_timeout=1,
                )
            return redis_async.Redis(connection_pool=self._redis_pool)
        except Exception:
            return None

    async def get_cached_permission(
        self,
        ctx: RequestContext,
        resource_type: str,
        resource_id: str,
        action: str,
    ) -> bool | None:
        """Get cached permission check result.

        Args:
            ctx: Request context.
            resource_type: Resource type.
            resource_id: Resource ID.
            action: Action.

        Returns:
            True if allowed, False if denied, None if not cached.
        """
        redis = await self._get_redis()
        if not redis:
            return None

        cache_key = self._cache_key(ctx, resource_type, resource_id, action)
        try:
            cached = await redis.get(cache_key)
            if cached is not None:
                return cached == "1"
        except Exception:
            pass
        return None

    async def set_cached_permission(
        self,
        ctx: RequestContext,
        resource_type: str,
        resource_id: str,
        action: str,
        allowed: bool,
    ) -> None:
        """Cache permission check result.

        Args:
            ctx: Request context.
            resource_type: Resource type.
            resource_id: Resource ID.
            action: Action.
            allowed: Whether action is allowed.
        """
        redis = await self._get_redis()
        if not redis:
            return

        cache_key = self._cache_key(ctx, resource_type, resource_id, action)
        try:
            await redis.setex(
                cache_key,
                self._cache_ttl,
                "1" if allowed else "0",
            )
        except Exception:
            pass

    def _cache_key(
        self,
        ctx: RequestContext,
        resource_type: str,
        resource_id: str,
        action: str,
    ) -> str:
        # The credential scope must be part of the identity: without it a
        # decision computed for an unrestricted session would be replayed
        # for a scoped API key of the same user, and vice versa.
        scope_signature = (
            "-" if ctx.scopes is None else ("+".join(sorted(ctx.scopes)) or "none")
        )
        return (
            f"perm:{PERMISSION_CACHE_VERSION}:{ctx.user_id}:"
            f"{ctx.tenant_id}:{ctx.workspace_id}:"
            f"{ctx.tenant_role or ''}:{ctx.workspace_role or ''}:"
            f"{scope_signature}:"
            f"{resource_type}:{resource_id}:{action}"
        )

    async def invalidate_permission(
        self,
        ctx: RequestContext,
        user_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> None:
        """Invalidate cached permissions.

        Args:
            ctx: Tenant and workspace scope to invalidate.
            user_id: Optional user ID (if None, invalidate all users).
            resource_type: Optional resource type.
            resource_id: Optional resource ID.
        """
        redis = await self._get_redis()
        if not redis:
            return

        try:
            patterns: list[str] = []
            aliases = _resource_type_aliases(resource_type) if resource_type else ()
            if user_id and resource_type and resource_id:
                patterns = [
                    f"perm:{PERMISSION_CACHE_VERSION}:{user_id}:"
                    f"{ctx.tenant_id}:{ctx.workspace_id}:*:*:*:{alias}:{resource_id}:*"
                    for alias in aliases
                ]
            elif user_id and resource_type:
                patterns = [
                    f"perm:{PERMISSION_CACHE_VERSION}:{user_id}:"
                    f"{ctx.tenant_id}:{ctx.workspace_id}:*:*:*:{alias}:*"
                    for alias in aliases
                ]
            elif user_id:
                patterns = [
                    f"perm:{PERMISSION_CACHE_VERSION}:{user_id}:"
                    f"{ctx.tenant_id}:{ctx.workspace_id}:*"
                ]
            else:
                patterns = [
                    f"perm:{PERMISSION_CACHE_VERSION}:*:"
                    f"{ctx.tenant_id}:{ctx.workspace_id}:*"
                ]

            # Redis SCAN and delete
            for pattern in patterns:
                async for key in redis.scan_iter(match=pattern):
                    await redis.delete(key)
        except Exception:
            pass


# Global permission cache instance
_permission_cache: PermissionCache | None = None
def get_permission_cache() -> PermissionCache:
    """Get or create global permission cache instance.

    Returns:
        PermissionCache instance.
    """
    global _permission_cache
    if _permission_cache is None:
        _permission_cache = PermissionCache()
    return _permission_cache


async def check_resource_permission(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    action: str,
    resource_owner_id: str | None = None,
) -> None:
    """Check if user has permission to perform action on resource.

    Args:
        ctx: Request context.
        resource_type: Resource type (workflow, knowledge, model, etc.).
        resource_id: Resource ID.
        action: Action (read, write, delete, execute, publish, create, update, run).
        resource_owner_id: Optional resource owner ID (for ownership checks).

    Raises:
        ForbiddenError: If permission denied.
    """
    # Check cache first
    cache = get_permission_cache()
    cached = await cache.get_cached_permission(
        ctx=ctx,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
    )

    if cached is not None:
        if not cached:
            raise ForbiddenError(
                f"Permission denied: {action} on {resource_type} {resource_id}",
                {
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "action": action,
                }
            )
        return

    action_key = _normalize_action(action)
    effective_action = _resolve_effective_action(action_key)

    # Perform permission check
    allowed = False

    # Workspace owners/admins can do everything
    if ctx.is_workspace_owner() or ctx.is_workspace_admin():
        allowed = True
    elif ctx.is_workspace_dev():
        # Dev can read/write/execute/run, but not delete/publish
        if effective_action in (ACTION_READ, ACTION_WRITE, ACTION_EXECUTE):
            allowed = True
    elif ctx.can_read():
        # Viewer can only read
        if effective_action == ACTION_READ:
            allowed = True

    # A scope is a ceiling over every authority source: ownership and
    # explicit grants must not hand a scoped credential more than its scope,
    # or a read-only API key could still write resources its owner created.
    scope_allows = ctx.has_scope(_required_scope(effective_action))

    # Resource owner can do everything within scope (if resource_owner_id provided)
    if resource_owner_id and resource_owner_id == ctx.user_id and scope_allows:
        allowed = True

    granted_by_resource_grant = False
    if not allowed and scope_allows:
        granted_by_resource_grant = _check_resource_grant(
            ctx=ctx,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action_key,
            effective_action=effective_action,
        )
        if granted_by_resource_grant:
            allowed = True

    if not granted_by_resource_grant:
        await cache.set_cached_permission(
            ctx=ctx,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            allowed=allowed,
        )

    if not allowed:
        raise ForbiddenError(
            f"Permission denied: {action} on {resource_type} {resource_id}",
            {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
            }
        )


def _normalize_action(action: str) -> str:
    return action.strip().lower()


def _resolve_effective_action(action: str) -> str:
    if action in (ACTION_CREATE, ACTION_UPDATE):
        return ACTION_WRITE
    if action == ACTION_RUN:
        return ACTION_EXECUTE
    if action == ACTION_EXECUTE_ALIAS:
        return ACTION_EXECUTE
    return action


def _required_scope(effective_action: str) -> str:
    """Scope ceiling an action needs, mirroring the role ladder.

    The ladder grants read to read-scoped viewers, write/execute to
    write-scoped devs, and delete/publish only to admin-scoped owners and
    admins. Ownership and explicit grants must clear the same bar, or a
    scoped credential escalates through them.
    """

    if effective_action == ACTION_READ:
        return "read"
    if effective_action in (ACTION_WRITE, ACTION_EXECUTE):
        return "write"
    return "admin"


def _check_resource_grant(
    *,
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    action: str,
    effective_action: str,
) -> bool:
    provider = get_resource_grant_provider()
    if provider is None:
        return False
    try:
        for alias in _resource_type_aliases(resource_type):
            if provider.allows_resource_action(
                ctx=ctx,
                resource_type=alias,
                resource_id=resource_id,
                action=action,
                effective_action=effective_action,
            ):
                return True
        return False
    except Exception:
        return False


async def require_resource_read_async(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: str | None = None,
) -> None:
    """Require read permission on resource (async)."""
    await _require_resource_action_async(ctx, resource_type, resource_id, ACTION_READ, resource_owner_id)


async def require_resource_write_async(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: str | None = None,
) -> None:
    """Require write permission on resource (async)."""
    await _require_resource_action_async(ctx, resource_type, resource_id, ACTION_WRITE, resource_owner_id)


async def require_resource_delete_async(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: str | None = None,
) -> None:
    """Require delete permission on resource (async)."""
    await _require_resource_action_async(ctx, resource_type, resource_id, ACTION_DELETE, resource_owner_id)


async def require_resource_execute_async(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: str | None = None,
) -> None:
    """Require execute permission on resource (async)."""
    await _require_resource_action_async(ctx, resource_type, resource_id, ACTION_EXECUTE, resource_owner_id)


async def require_resource_create_async(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: str | None = None,
) -> None:
    """Require create permission on resource (async)."""
    await _require_resource_action_async(ctx, resource_type, resource_id, ACTION_CREATE, resource_owner_id)


async def require_resource_update_async(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: str | None = None,
) -> None:
    """Require update permission on resource (async)."""
    await _require_resource_action_async(ctx, resource_type, resource_id, ACTION_UPDATE, resource_owner_id)


async def require_resource_run_async(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: str | None = None,
) -> None:
    """Require run permission on resource (async)."""
    await _require_resource_action_async(ctx, resource_type, resource_id, ACTION_RUN, resource_owner_id)


async def _require_resource_action_async(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    action: str,
    resource_owner_id: str | None = None,
) -> None:
    """Require permission on resource (async)."""
    await check_resource_permission(
        ctx,
        resource_type,
        resource_id,
        action,
        resource_owner_id,
    )
