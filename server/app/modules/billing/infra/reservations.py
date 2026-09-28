"""Budget holds for calls admitted but not yet costed.

Every admitted call holds each hard-stop budget it was checked against: one
sorted-set member per budget, scored by when the hold expires. The check and
the hold are one Redis script, so two callers cannot both see a free slot and
both take it. A hold is released as soon as the call's cost is committed (see
``budget_holds``); a hold nobody releases, for a call that failed or a process
that died, expires on its own.

When Redis is unreachable the holds are kept in this process instead, so a
single API process still keeps concurrent callers within a limit; replicas do
not see each other's holds until Redis is back.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Awaitable, Sequence
from typing import Any, cast
from uuid import uuid4

import redis.asyncio as redis_async

from app.kernel.ports.common.redis_client import shared_redis
from app.modules.billing.application.budgets import HoldGrant, HoldRefusal, HoldRequest

logger = logging.getLogger(__name__)

# KEYS: one sorted set per budget.
# ARGV: now, expires_at, member, key ttl (seconds), then one capacity per key
# (-1 for unbounded). A key refuses when it already holds its capacity.
_ACQUIRE = """
local now = tonumber(ARGV[1])
local expires_at = tonumber(ARGV[2])
local member = ARGV[3]
local key_ttl = tonumber(ARGV[4])
for i, key in ipairs(KEYS) do
    redis.call('ZREMRANGEBYSCORE', key, '-inf', now)
    local capacity = tonumber(ARGV[4 + i])
    local held = redis.call('ZCARD', key)
    if capacity >= 0 and held >= capacity then
        return {i, held}
    end
end
for _, key in ipairs(KEYS) do
    redis.call('ZADD', key, expires_at, member)
    redis.call('EXPIRE', key, key_ttl)
end
return {0, 0}
"""


def _key(budget_id: str) -> str:
    return f"budget:inflight:{budget_id}"


class LocalBudgetReservations:
    """Holds kept in this process, for when Redis cannot be reached."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._holds: dict[str, dict[str, float]] = {}

    def _live(self, budget_id: str, now: float) -> dict[str, float]:
        holds = self._holds.setdefault(budget_id, {})
        for member in [member for member, expires_at in holds.items() if expires_at <= now]:
            del holds[member]
        return holds

    def held(self, budget_id: str) -> int:
        with self._lock:
            return len(self._live(budget_id, time.time()))

    async def acquire(
        self, requests: Sequence[HoldRequest], *, ttl_seconds: float
    ) -> HoldGrant | HoldRefusal:
        now = time.time()
        member = uuid4().hex
        with self._lock:
            for request in requests:
                held = len(self._live(request.budget_id, now))
                if request.capacity is not None and held >= request.capacity:
                    return HoldRefusal(request.budget_id, held)
            for request in requests:
                self._holds[request.budget_id][member] = now + ttl_seconds
        return HoldGrant(member, tuple(request.budget_id for request in requests), "local")

    async def release(self, grant: HoldGrant) -> None:
        with self._lock:
            for budget_id in grant.budget_ids:
                self._holds.get(budget_id, {}).pop(grant.token, None)


class RedisBudgetReservations:
    """Holds in Redis, shared by every API and worker process."""

    def __init__(
        self,
        redis_client: redis_async.Redis | None = None,
        *,
        fallback: LocalBudgetReservations | None = None,
    ) -> None:
        self._redis = redis_client
        self.fallback = fallback if fallback is not None else LocalBudgetReservations()

    def _client(self) -> redis_async.Redis:
        return self._redis if self._redis is not None else shared_redis()

    async def acquire(
        self, requests: Sequence[HoldRequest], *, ttl_seconds: float
    ) -> HoldGrant | HoldRefusal:
        if not requests:
            return HoldGrant(uuid4().hex, (), "redis")
        now = time.time()
        member = uuid4().hex
        capacities = [str(-1 if request.capacity is None else request.capacity) for request in requests]
        try:
            script = self._client().eval(
                _ACQUIRE,
                len(requests),
                *[_key(request.budget_id) for request in requests],
                str(now),
                str(now + ttl_seconds),
                member,
                str(max(1, int(ttl_seconds * 2))),
                *capacities,
            )
            result = await cast(Awaitable[list[Any]], script)
        except Exception as exc:
            logger.warning("Budget holds unavailable in Redis, holding in this process: %s", exc)
            return await self.fallback.acquire(requests, ttl_seconds=ttl_seconds)
        refused_at, held = (int(value) for value in result)
        if refused_at:
            return HoldRefusal(requests[refused_at - 1].budget_id, held)
        return HoldGrant(member, tuple(request.budget_id for request in requests), "redis")

    async def release(self, grant: HoldGrant) -> None:
        if grant.backend == "local":
            await self.fallback.release(grant)
            return
        if not grant.budget_ids:
            return
        try:
            async with self._client().pipeline(transaction=True) as pipe:
                for budget_id in grant.budget_ids:
                    pipe.zrem(_key(budget_id), grant.token)
                await pipe.execute()
        except Exception as exc:
            # The hold still expires on its own.
            logger.warning("Budget hold not released: %s", exc)
