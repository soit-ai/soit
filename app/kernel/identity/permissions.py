""" permissions

Resource-level permission checks and caching.
"""

from typing import Optional, Set
import redis.asyncio as redis_async
from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ForbiddenError
from app.kernel.config.settings import settings


# Resource types
RESOURCE_WORKFLOW = "workflow"
RESOURCE_DATASET = "dataset"
RESOURCE_MODEL = "model"
RESOURCE_PLUGIN = "plugin"
RESOURCE_APP = "app"

# Actions
ACTION_READ = "read"
ACTION_WRITE = "write"
ACTION_DELETE = "delete"
ACTION_EXECUTE = "execute"
ACTION_PUBLISH = "publish"


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
        if self._redis is not None:
            return self._redis
        
        try:
            if self._redis_pool is None:
                self._redis_pool = redis_async.ConnectionPool.from_url(
                    settings.redis_url,
                    decode_responses=True,
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
            if user_id and resource_type and resource_id:
                # Invalidate specific permission
                pattern = f"perm:{user_id}:{resource_type}:{resource_id}:*"
            elif user_id and resource_type:
                # Invalidate all permissions for user+resource_type
                pattern = f"perm:{user_id}:{resource_type}:*"
            elif user_id:
                # Invalidate all permissions for user
                pattern = f"perm:{user_id}:*"
            else:
                # Invalidate all permissions (use with caution)
                pattern = "perm:*"
            
            # Redis SCAN and delete
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
        resource_type: Resource type (workflow, dataset, model, etc.).
        resource_id: Resource ID.
        action: Action (read, write, delete, execute, publish).
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
    
    # Perform permission check
    allowed = False
    
    # Workspace owners/maintainers can do everything
    if ctx.is_workspace_owner():
        allowed = True
    elif ctx.is_workspace_maintainer():
        # Maintainers can read/write/execute, but not delete/publish
        if action in (ACTION_READ, ACTION_WRITE, ACTION_EXECUTE):
            allowed = True
    elif ctx.can_read():
        # Readers can only read
        if action == ACTION_READ:
            allowed = True
    
    # Resource owner can do everything (if resource_owner_id provided)
    if resource_owner_id and resource_owner_id == ctx.user_id:
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


def require_resource_read(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Require read permission on resource.
    
    Args:
        ctx: Request context.
        resource_type: Resource type.
        resource_id: Resource ID.
        resource_owner_id: Optional resource owner ID.
        
    Raises:
        ForbiddenError: If permission denied.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If event loop is running, schedule coroutine
            import asyncio
            task = asyncio.create_task(
                check_resource_permission(ctx, resource_type, resource_id, ACTION_READ, resource_owner_id)
            )
            # For sync context, we'll need to handle this differently
            # For now, do sync check
            if not ctx.can_read():
                raise ForbiddenError(f"Read permission denied on {resource_type} {resource_id}")
        else:
            loop.run_until_complete(
                check_resource_permission(ctx, resource_type, resource_id, ACTION_READ, resource_owner_id)
            )
    except RuntimeError:
        # No event loop, do sync check
        if not ctx.can_read():
            raise ForbiddenError(f"Read permission denied on {resource_type} {resource_id}")


def require_resource_write(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Require write permission on resource.
    
    Args:
        ctx: Request context.
        resource_type: Resource type.
        resource_id: Resource ID.
        resource_owner_id: Optional resource owner ID.
        
    Raises:
        ForbiddenError: If permission denied.
    """
    if not ctx.can_write():
        raise ForbiddenError(f"Write permission denied on {resource_type} {resource_id}")


def require_resource_delete(
    ctx: RequestContext,
    resource_type: str,
    resource_id: str,
    resource_owner_id: Optional[str] = None,
) -> None:
    """Require delete permission on resource.
    
    Args:
        ctx: Request context.
        resource_type: Resource type.
        resource_id: Resource ID.
        resource_owner_id: Optional resource owner ID.
        
    Raises:
        ForbiddenError: If permission denied.
    """
    if not ctx.is_workspace_owner():
        if resource_owner_id and resource_owner_id != ctx.user_id:
            raise ForbiddenError(f"Delete permission denied on {resource_type} {resource_id}")
        if not ctx.is_workspace_owner():
            raise ForbiddenError(f"Delete permission denied on {resource_type} {resource_id}")

