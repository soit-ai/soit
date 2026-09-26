""" usage_counter

Per-day usage totals in Redis, for quotas counted in units rather than calls.

A token quota cannot be checked the way a request quota is: the tokens a call
uses are known only when it returns. The total is therefore read before a call
and added to after it, so a quota can be overrun by at most the calls already
in flight when it was reached. Days are UTC days, and a total resets at UTC
midnight.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, time, timedelta

import redis.asyncio as redis_async

from app.kernel.commons.time import utc_now
from app.kernel.ports.common.redis_client import shared_redis

logger = logging.getLogger(__name__)

# Two days, so the bucket outlives its day wherever the reader's clock is.
_BUCKET_TTL_SECONDS = 2 * 86400


def seconds_until_next_utc_day(now: datetime) -> int:
    """Seconds from ``now`` until the next UTC midnight, at least one."""

    moment = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    midnight = datetime.combine((moment + timedelta(days=1)).date(), time.min, tzinfo=UTC)
    return max(1, int((midnight - moment.astimezone(UTC)).total_seconds()))


class DailyUsageCounter:
    """Usage totals per key and UTC day.

    Like the rate limiter it fails open: when Redis is unreachable a total
    reads as zero and an addition is dropped, with a warning, rather than
    refusing every call.
    """

    def __init__(self, redis_client: redis_async.Redis | None = None) -> None:
        self._redis = redis_client

    def _client(self) -> redis_async.Redis:
        return self._redis if self._redis is not None else shared_redis()

    @staticmethod
    def _bucket(key: str, now: datetime) -> str:
        return f"usage:{key}:{now.astimezone(UTC):%Y%m%d}"

    async def total(self, key: str, *, now: datetime | None = None) -> int:
        """What ``key`` has used so far on ``now``'s UTC day."""

        try:
            value = await self._client().get(self._bucket(key, now or utc_now()))
        except Exception as exc:
            logger.warning("Usage counter unavailable, reading zero: %s", exc)
            return 0
        return int(value or 0)

    async def add(self, key: str, amount: int, *, now: datetime | None = None) -> None:
        """Add ``amount`` to ``key``'s total for ``now``'s UTC day."""

        if amount <= 0:
            return
        bucket = self._bucket(key, now or utc_now())
        try:
            client = self._client()
            async with client.pipeline(transaction=True) as pipe:
                pipe.incrby(bucket, amount)
                pipe.expire(bucket, _BUCKET_TTL_SECONDS)
                await pipe.execute()
        except Exception as exc:
            logger.warning("Usage counter unavailable, usage not counted: %s", exc)
