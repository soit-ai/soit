""" rate_limiter

Redis-based rate limiter using sliding window algorithm.
"""

import time
from typing import Optional, Union
import redis.asyncio as redis_async
from app.kernel.config.settings import settings
from app.kernel.commons.errors import ForbiddenError


class RateLimiter:
    """Rate limiter using Redis sliding window algorithm."""
    
    def __init__(self, redis_client: Optional[redis_async.Redis] = None):
        """Initialize rate limiter.
        
        Args:
            redis_client: Optional Redis client. If None, creates a new connection.
        """
        self._redis: Optional[redis_async.Redis] = redis_client
        self._redis_pool: Optional[redis_async.ConnectionPool] = None
    
    async def _get_redis(self) -> redis_async.Redis:
        """Get or create Redis client.
        
        Returns:
            Redis client instance.
        """
        if self._redis is not None:
            return self._redis
        
        if self._redis_pool is None:
            self._redis_pool = redis_async.ConnectionPool.from_url(
                settings.redis_url,
                decode_responses=False,  # We need bytes for Lua scripts
            )
        
        return redis_async.Redis(connection_pool=self._redis_pool)
    
    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> bool:
        """Check if request is within rate limit using sliding window.
        
        Args:
            key: Rate limit key (e.g., "tenant:123:llm").
            limit: Maximum number of requests allowed.
            window_seconds: Time window in seconds.
            
        Returns:
            True if within limit, False if rate limit exceeded.
            
        Raises:
            ForbiddenError: If rate limit is exceeded.
        """
        redis = await self._get_redis()
        
        # Use sliding window log algorithm
        # Key format: "ratelimit:{key}"
        redis_key = f"ratelimit:{key}"
        now = time.time()
        window_start = now - window_seconds
        
        # Lua script for atomic operation
        lua_script = """
        local key = KEYS[1]
        local window_start = tonumber(ARGV[1])
        local now = tonumber(ARGV[2])
        local limit = tonumber(ARGV[3])
        local window_seconds = tonumber(ARGV[4])
        
        -- Remove old entries
        redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
        
        -- Count current requests in window
        local count = redis.call('ZCARD', key)
        
        if count < limit then
            -- Add current request
            redis.call('ZADD', key, now, now)
            -- Set expiration
            redis.call('EXPIRE', key, window_seconds)
            return 1
        else
            return 0
        end
        """
        
        try:
            result = await redis.eval(
                lua_script,
                1,  # Number of keys
                redis_key,
                str(window_start),
                str(now),
                str(limit),
                str(window_seconds),
            )
            
            if result == 0:
                # Rate limit exceeded
                # Get remaining time
                ttl = await redis.ttl(redis_key)
                raise ForbiddenError(
                    f"Rate limit exceeded: {limit} requests per {window_seconds} seconds",
                    {
                        "limit": limit,
                        "window_seconds": window_seconds,
                        "retry_after": ttl if ttl > 0 else window_seconds,
                    }
                )
            
            return True
        except ForbiddenError:
            raise
        except Exception as e:
            # If Redis is unavailable, log and allow request (fail-open)
            # In production, you might want to fail-closed
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Rate limiter error (allowing request): {e}")
            return True
    
    async def get_remaining(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> int:
        """Get remaining requests in current window.
        
        Args:
            key: Rate limit key.
            limit: Maximum number of requests allowed.
            window_seconds: Time window in seconds.
            
        Returns:
            Number of remaining requests.
        """
        redis = await self._get_redis()
        redis_key = f"ratelimit:{key}"
        now = time.time()
        window_start = now - window_seconds
        
        # Remove old entries and count
        await redis.zremrangebyscore(redis_key, 0, window_start)
        count = await redis.zcard(redis_key)
        
        return max(0, limit - count)
    
    async def reset(self, key: str) -> None:
        """Reset rate limit for a key.
        
        Args:
            key: Rate limit key to reset.
        """
        redis = await self._get_redis()
        redis_key = f"ratelimit:{key}"
        await redis.delete(redis_key)
    
    async def close(self) -> None:
        """Close Redis connections."""
        if self._redis_pool:
            await self._redis_pool.disconnect()
            self._redis_pool = None

