"""Daily usage totals count units per UTC day and fail open."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.kernel.ports.common.usage_counter import (
    DailyUsageCounter,
    seconds_until_next_utc_day,
)


class _Pipeline:
    def __init__(self, store: _Redis) -> None:
        self.store = store
        self.ops: list[tuple[str, str, int]] = []

    async def __aenter__(self) -> _Pipeline:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    def incrby(self, key: str, amount: int) -> None:
        self.ops.append(("incrby", key, amount))

    def expire(self, key: str, seconds: int) -> None:
        self.ops.append(("expire", key, seconds))

    async def execute(self) -> None:
        for op, key, value in self.ops:
            if op == "incrby":
                self.store.values[key] = self.store.values.get(key, 0) + value
            else:
                self.store.ttls[key] = value


class _Redis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> Any:
        value = self.values.get(key)
        return None if value is None else str(value).encode()

    def pipeline(self, transaction: bool = True) -> _Pipeline:
        del transaction
        return _Pipeline(self)


class _Down:
    async def get(self, key: str) -> Any:
        raise ConnectionError("redis is down")

    def pipeline(self, transaction: bool = True) -> Any:
        raise ConnectionError("redis is down")


@pytest.mark.asyncio
async def test_totals_accumulate_within_a_utc_day_and_reset_after_it() -> None:
    redis = _Redis()
    counter = DailyUsageCounter(redis_client=redis)  # type: ignore[arg-type]
    morning = datetime(2026, 9, 27, 1, 0, tzinfo=UTC)
    evening = datetime(2026, 9, 27, 23, 59, tzinfo=UTC)
    next_day = datetime(2026, 9, 28, 0, 1, tzinfo=UTC)

    await counter.add("tokens:api_key:k", 400, now=morning)
    await counter.add("tokens:api_key:k", 100, now=evening)
    await counter.add("tokens:api_key:k", 0, now=evening)

    assert await counter.total("tokens:api_key:k", now=evening) == 500
    assert await counter.total("tokens:api_key:k", now=next_day) == 0
    assert redis.ttls == {"usage:tokens:api_key:k:20260927": 2 * 86400}


@pytest.mark.asyncio
async def test_an_unreachable_store_reads_zero_and_drops_additions() -> None:
    counter = DailyUsageCounter(redis_client=_Down())  # type: ignore[arg-type]

    await counter.add("tokens:api_key:k", 10)

    assert await counter.total("tokens:api_key:k") == 0


def test_retry_after_points_at_the_next_utc_midnight() -> None:
    assert seconds_until_next_utc_day(datetime(2026, 9, 27, 23, 0, tzinfo=UTC)) == 3600
    assert seconds_until_next_utc_day(datetime(2026, 9, 27, 23, 59, 59, 900000, tzinfo=UTC)) == 1
