""" redis_client

One Redis connection pool per event loop, shared by a process's limiters.

Policy gateways are built per request, and a pool per gateway opened sockets
for every model call without ever closing them. A single pool per process
fails the other way: a pool belongs to the loop that first used it, so a
worker that runs a fresh loop per job would see every call fail, and the
limiters, which fail open, would stop limiting.
"""

from __future__ import annotations

import asyncio
import weakref

import redis.asyncio as redis_async

from app.settings.settings import settings

_pools: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, redis_async.ConnectionPool] = (
    weakref.WeakKeyDictionary()
)


def shared_redis() -> redis_async.Redis:
    """A client on the running loop's shared pool."""

    loop = asyncio.get_running_loop()
    pool = _pools.get(loop)
    if pool is None:
        pool = redis_async.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=False,
        )
        _pools[loop] = pool
    return redis_async.Redis(connection_pool=pool)
