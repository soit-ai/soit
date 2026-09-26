"""Budget reservations held in Redis while admitted calls are in flight."""

from __future__ import annotations

import logging
import time
from uuid import uuid4

import redis.asyncio as redis_async

from app.kernel.ports.common.redis_client import shared_redis

logger = logging.getLogger(__name__)


class RedisBudgetReservations:
    """One sorted-set member per admitted call, scored by when it expires.

    A reservation is never released explicitly: it expires after ``ttl``,
    by which time the call has normally recorded its cost. Near a limit that
    counts a finished call twice for a moment, which errs on the side of the
    limit. Like the rate limiter, it fails open when Redis is unreachable.
    """

    def __init__(self, redis_client: redis_async.Redis | None = None, *, ttl_seconds: int = 60) -> None:
        self._redis = redis_client
        self.ttl_seconds = ttl_seconds

    def _client(self) -> redis_async.Redis:
        return self._redis if self._redis is not None else shared_redis()

    @staticmethod
    def _key(budget_id: str) -> str:
        return f"budget:inflight:{budget_id}"

    async def in_flight(self, budget_id: str) -> int:
        key = self._key(budget_id)
        try:
            client = self._client()
            await client.zremrangebyscore(key, 0, time.time())
            return int(await client.zcard(key))
        except Exception as exc:
            logger.warning("Budget reservations unavailable, counting none: %s", exc)
            return 0

    async def reserve(self, budget_id: str) -> None:
        key = self._key(budget_id)
        try:
            client = self._client()
            async with client.pipeline(transaction=True) as pipe:
                pipe.zadd(key, {uuid4().hex: time.time() + self.ttl_seconds})
                pipe.expire(key, self.ttl_seconds * 2)
                await pipe.execute()
        except Exception as exc:
            logger.warning("Budget reservation not recorded: %s", exc)
