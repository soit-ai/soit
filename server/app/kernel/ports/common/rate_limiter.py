""" rate_limiter

Redis-based rate limiter using sliding window algorithm.
"""

import math
import secrets
import time
from typing import Any, cast

import redis.asyncio as redis_async

from app.kernel.commons.errors import RateLimitExceededError
from app.kernel.ports.common.redis_client import shared_redis


class RateLimiter:
    """Rate limiter using Redis sliding window algorithm."""

    def __init__(self, redis_client: redis_async.Redis | None = None):
        """Initialize rate limiter.

        Args:
            redis_client: Optional Redis client. If None, the running loop's
                shared pool is used, so building a limiter per request opens
                no connections of its own.
        """
        self._redis: redis_async.Redis | None = redis_client

    async def _get_redis(self) -> redis_async.Redis:
        """Get the Redis client.

        Returns:
            Redis client instance.
        """
        if self._redis is not None:
            return self._redis
        return shared_redis()

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
            RateLimitExceededError: If rate limit is exceeded.
        """
        redis = await self._get_redis()

        # Use sliding window log algorithm
        # Key format: "ratelimit:{key}"
        redis_key = f"ratelimit:{key}"
        now = time.time()
        window_start = now - window_seconds

        # Each request is its own member: two requests in the same instant
        # are two requests. A refusal returns when the request whose leaving
        # frees a slot was made: the oldest while the window holds the limit,
        # a later one when the limit was lowered below what it holds. The
        # key's TTL says only when the last one leaves.
        lua_script = """
        local key = KEYS[1]
        local window_start = tonumber(ARGV[1])
        local now = tonumber(ARGV[2])
        local limit = tonumber(ARGV[3])
        local window_seconds = tonumber(ARGV[4])

        redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
        local count = redis.call('ZCARD', key)

        if count < limit then
            redis.call('ZADD', key, now, ARGV[5])
            redis.call('EXPIRE', key, window_seconds)
            return {1, ARGV[2]}
        end
        local freeing = redis.call('ZRANGE', key, count - limit, count - limit, 'WITHSCORES')
        return {0, freeing[2] or ARGV[2]}
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
                f"{now}:{secrets.token_hex(8)}",
            )

            allowed, freeing_at = cast(list[Any], result)
            if int(allowed) == 0:
                retry_after = max(1, math.ceil(float(freeing_at) + window_seconds - now))
                raise RateLimitExceededError(
                    f"Rate limit exceeded: {limit} requests per {window_seconds} seconds",
                    {
                        "limit": limit,
                        "window_seconds": window_seconds,
                        "retry_after": min(retry_after, window_seconds),
                    }
                )

            return True
        except RateLimitExceededError:
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
        """Release nothing: connections belong to the loop's shared pool."""

