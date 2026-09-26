"""Limiters share one Redis pool per event loop instead of one per request."""

from __future__ import annotations

import asyncio

import redis.asyncio as redis_async

from app.kernel.ports.common.rate_limiter import RateLimiter
from app.kernel.ports.common.redis_client import shared_redis


def test_clients_on_one_loop_share_a_pool() -> None:
    async def pools() -> tuple[redis_async.ConnectionPool, redis_async.ConnectionPool]:
        return shared_redis().connection_pool, shared_redis().connection_pool

    first, second = asyncio.run(pools())

    assert first is second


def test_each_loop_gets_its_own_pool() -> None:
    async def pool() -> redis_async.ConnectionPool:
        return shared_redis().connection_pool

    held = asyncio.run(pool())

    # A pool belongs to the loop that made it; a fresh loop must not reuse it.
    assert asyncio.run(pool()) is not held


def test_a_limiter_built_per_request_uses_the_shared_pool() -> None:
    async def pools() -> tuple[redis_async.ConnectionPool, redis_async.ConnectionPool]:
        first = await RateLimiter()._get_redis()
        second = await RateLimiter()._get_redis()
        return first.connection_pool, second.connection_pool

    first, second = asyncio.run(pools())

    assert first is second
