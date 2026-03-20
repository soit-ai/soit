""" permissions

Resource-level permission checks and caching.
"""

from typing import Optional, Set
import asyncio
import os
import redis.asyncio as redis_async
from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ForbiddenError
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


def _resource_type_aliases(resource_type: str) -> tuple[str, ...]:
    normalized = (resource_type or "").strip().lower()
    return (normalized,)


class PermissionCache:
    """Permission cache using Redis."""
    
    def __init__(self, redis_client: Optional[redis_async.Redis] = None):
        """Initialize permission cache.
        
        Args:
            redis_client: Optional Redis client.
        """
        self._redis: Optional[redis_async.Redis] = redis_client
        self._redis_pool: Optional[redis_async.ConnectionPool] = None
        self._cache_ttl = 300  # 5 minutes
    
    async def _get_redis(self) -> Optional[redis_async.Redis]:
        """Get or create Redis client.
        
        Returns:
            Redis client instance or None if Redis unavailable.
        """
        if os.getenv("PYTEST_CURRENT_TEST"):
            return None
        if self._redis is not None:
            return self._redis
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
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
    ) -> Optional[bool]:
        """Get cached permission check result.
        
        Args:
            user_id: User ID.
            resource_type: Resource type.
            resource_id: Resource ID.
            action: Action.
            
        Returns:
            True if allowed, False if denied, None if not cached.
        """
        redis = await self._get_redis()
        if not redis:
            return None
        
        cache_key = f"perm:{user_id}:{resource_type}:{resource_id}:{action}"
        try:
            cached = await redis.get(cache_key)
            if cached is not None:
                return cached == "1"
        except Exception:
            pass
        return None
    
    async def set_cached_permission(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        allowed: bool,
    ) -> None:
        """Cache permission check result.
        
        Args:
            user_id: User ID.
            resource_type: Resource type.
            resource_id: Resource ID.
            action: Action.
            allowed: Whether action is allowed.
        """
        redis = await self._get_redis()
        if not redis:
            return
        
        cache_key = f"perm:{user_id}:{resource_type}:{resource_id}:{action}"
        try:
            await redis.setex(
                cache_key,
                self._cache_ttl,
                "1" if allowed else "0",
            )
        except Exception:
            pass
    
    async def invalidate_permission(
        self,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
    ) -> None:
        """Invalidate cached permissions.
        
        Args:
            user_id: Optional user ID (if None, invalidate all users).
            resource_type: Optional resource type.
            resource_id: Optional resource ID.
        """
        redis = await self._get_redis()
        if not redis:
            return
        
        try:
            patterns: list[str] = []
            aliases = _resource_type_aliases(resource_type) if resource_type else tuple()
            if user_id and resource_type and resource_id:
                patterns = [f"perm:{user_id}:{alias}:{resource_id}:*" for alias in aliases]
            elif user_id and resource_type:
                patterns = [f"perm:{user_id}:{alias}:*" for alias in aliases]
            elif user_id:
                # Invalidate all permissions for user
                patterns = [f"perm:{user_id}:*"]
            else:
                # Invalidate all permissions (use with caution)
                patterns = ["perm:*"]
            
            # Redis SCAN and delete
            for pattern in patterns:
                async for key in redis.scan_iter(match=pattern):
                    await redis.delete(key)
        except Exception:
            pass


# Global permission cache instance
_permission_cache: Optional[PermissionCache] = None
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
    resource_owner_id: Optional[str] = None,
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
        user_id=ctx.user_id,
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
    
    # Resource owner can do everything (if resource_owner_id provided)
    if resource_owner_id and resource_owner_id == ctx.user_id:
        allowed = True

    if not allowed:
        grant_allowed = _check_resource_grant(
            ctx=ctx,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action_key,
            effective_action=effective_action,
        )
        if grant_allowed:
            allowed = True
    
    # Cache result
    await cache.set_cached_permission(
        user_id=ctx.user_id,
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


def _check_resource_grant(
    *,
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    action: str,
    effective_action: str,
) -> bool:
    try:
        from app.infra.db.session import get_db_sync
        from app.modules.identity.infra.repository import ResourceGrantRepository
    except Exception:
        return False

    db = None
    try:
        db = get_db_sync()
        repo = ResourceGrantRepository(db, ctx)
        for alias in _resource_type_aliases(resource_type):
            grant = repo.get_by_resource_user(alias, resource_id, ctx.user_id)
            if not grant:
                continue
            allowed_actions = {_normalize_action(item) for item in (grant.actions or [])}
            if "*" in allowed_actions:
                return True
            if action in allowed_actions or effective_action in allowed_actions:
                return True
        return False
    except Exception:
        return False
    finally:
        if db:
            try:
                db.close()
            except Exception:
                pass


def require_resource_read(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Deprecated sync permission check (disabled)."""
    raise RuntimeError("require_resource_read is disabled; use await require_resource_read_async")


def require_resource_write(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Deprecated sync permission check (disabled)."""
    raise RuntimeError("require_resource_write is disabled; use await require_resource_write_async")


def require_resource_delete(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Deprecated sync permission check (disabled)."""
    raise RuntimeError("require_resource_delete is disabled; use await require_resource_delete_async")


def require_resource_execute(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Deprecated sync permission check (disabled)."""
    raise RuntimeError("require_resource_execute is disabled; use await require_resource_execute_async")


def require_resource_create(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Deprecated sync permission check (disabled)."""
    raise RuntimeError("require_resource_create is disabled; use await require_resource_create_async")


def require_resource_update(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Deprecated sync permission check (disabled)."""
    raise RuntimeError("require_resource_update is disabled; use await require_resource_update_async")


def require_resource_run(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Deprecated sync permission check (disabled)."""
    raise RuntimeError("require_resource_run is disabled; use await require_resource_run_async")


async def require_resource_read_async(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Require read permission on resource (async)."""
    await _require_resource_action_async(ctx, resource_type, resource_id, ACTION_READ, resource_owner_id)


async def require_resource_write_async(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Require write permission on resource (async)."""
    await _require_resource_action_async(ctx, resource_type, resource_id, ACTION_WRITE, resource_owner_id)


async def require_resource_delete_async(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Require delete permission on resource (async)."""
    await _require_resource_action_async(ctx, resource_type, resource_id, ACTION_DELETE, resource_owner_id)


async def require_resource_execute_async(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Require execute permission on resource (async)."""
    await _require_resource_action_async(ctx, resource_type, resource_id, ACTION_EXECUTE, resource_owner_id)


async def require_resource_create_async(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Require create permission on resource (async)."""
    await _require_resource_action_async(ctx, resource_type, resource_id, ACTION_CREATE, resource_owner_id)


async def require_resource_update_async(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Require update permission on resource (async)."""
    await _require_resource_action_async(ctx, resource_type, resource_id, ACTION_UPDATE, resource_owner_id)


async def require_resource_run_async(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Require run permission on resource (async)."""
    await _require_resource_action_async(ctx, resource_type, resource_id, ACTION_RUN, resource_owner_id)


async def _require_resource_action_async(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    action: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Require permission on resource (async)."""
    await check_resource_permission(
        ctx,
        resource_type,
        resource_id,
        action,
        resource_owner_id,
    )
