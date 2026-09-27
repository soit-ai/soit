""" test_rate_limiter

Unit tests for rate limiter.
"""

import time
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
import redis.asyncio as redis_async

from app.kernel.commons.errors import RateLimitExceededError
from app.kernel.ports.common.rate_limiter import RateLimiter


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis_client = AsyncMock(spec=redis_async.Redis)
    redis_client.eval = AsyncMock(return_value=[1, "0"])  # Allowed
    redis_client.ttl = AsyncMock(return_value=60)
    redis_client.zremrangebyscore = AsyncMock()
    redis_client.zcard = AsyncMock(return_value=0)
    redis_client.delete = AsyncMock()
    return redis_client


@pytest.mark.asyncio
async def test_rate_limit_allowed(mock_redis):
    """Test that request within limit is allowed."""
    limiter = RateLimiter(redis_client=mock_redis)

    result = await limiter.check_rate_limit(
        key="test_key",
        limit=10,
        window_seconds=60,
    )

    assert result is True


@pytest.mark.asyncio
async def test_rate_limit_exceeded(mock_redis):
    """Exceeding the limit raises RateLimitExceededError, which maps to HTTP 429."""
    # Refused; the oldest request in the window was made just now.
    mock_redis.eval = AsyncMock(return_value=[0, str(time.time())])

    limiter = RateLimiter(redis_client=mock_redis)

    with pytest.raises(RateLimitExceededError) as raised:
        await limiter.check_rate_limit(
            key="test_key",
            limit=10,
            window_seconds=60,
        )
    assert raised.value.code == "RATE_LIMIT_EXCEEDED"
    assert raised.value.details["limit"] == 10
    assert raised.value.details["retry_after"] > 0


@pytest.mark.asyncio
async def test_get_remaining(mock_redis):
    """Test getting remaining requests."""
    mock_redis.zcard = AsyncMock(return_value=5)

    limiter = RateLimiter(redis_client=mock_redis)

    remaining = await limiter.get_remaining(
        key="test_key",
        limit=10,
        window_seconds=60,
    )

    assert remaining == 5


@pytest.mark.asyncio
async def test_a_refusal_says_when_the_oldest_request_leaves_the_window(mock_redis):
    # The oldest of the day's requests was made 23 hours ago: a slot frees in
    # about an hour, not in the day the key's TTL would suggest.
    mock_redis.eval = AsyncMock(return_value=[0, str(time.time() - 23 * 3600)])

    limiter = RateLimiter(redis_client=mock_redis)
    with pytest.raises(RateLimitExceededError) as raised:
        await limiter.check_rate_limit(key="daily", limit=5, window_seconds=86400)

    assert 3500 <= raised.value.details["retry_after"] <= 3601
    mock_redis.ttl.assert_not_awaited()


@pytest.mark.asyncio
async def test_every_request_is_counted_as_its_own_member(mock_redis):
    # A sorted set keeps one member per value: requests recorded under their
    # timestamp alone collapse into one when they share an instant.
    limiter = RateLimiter(redis_client=mock_redis)

    await limiter.check_rate_limit(key="burst", limit=10, window_seconds=60)
    await limiter.check_rate_limit(key="burst", limit=10, window_seconds=60)

    members = [call.args[-1] for call in mock_redis.eval.await_args_list]
    assert len(set(members)) == 2



@pytest_asyncio.fixture
async def real_redis():
    """The Lua script runs only in Redis; these tests skip where none is reachable."""
    import secrets

    from app.settings.settings import settings

    client = redis_async.from_url(settings.redis_url, socket_connect_timeout=0.5, socket_timeout=2)
    try:
        await client.ping()
    except Exception:
        await client.aclose()
        pytest.skip("no Redis reachable")
    key = f"test:rate_limiter:{secrets.token_hex(6)}"
    yield client, key
    await client.delete(f"ratelimit:{key}")
    await client.aclose()


@pytest.mark.asyncio
async def test_requests_in_one_instant_are_each_counted(real_redis, monkeypatch):
    client, key = real_redis
    monkeypatch.setattr(time, "time", lambda: 1_000_000.0)
    limiter = RateLimiter(redis_client=client)

    results = []
    for _ in range(5):
        try:
            results.append(await limiter.check_rate_limit(key=key, limit=3, window_seconds=60))
        except RateLimitExceededError:
            results.append(False)

    assert results == [True, True, True, False, False]


@pytest.mark.asyncio
@pytest.mark.parametrize(("held", "limit", "wait"), [(3, 3, 3600), (10, 3, 8 * 3600)])
async def test_a_refusal_says_when_a_slot_frees(real_redis, held, limit, wait):
    # One request an hour for the last `held` hours. With the window full at
    # the limit, the oldest leaving frees a slot; with a limit lowered below
    # what the window holds, a slot frees only when enough have left.
    client, key = real_redis
    now = time.time()
    await client.zadd(
        f"ratelimit:{key}",
        {f"seed:{hour}": now - 86400 + (hour + 1) * 3600 for hour in range(held)},
    )
    limiter = RateLimiter(redis_client=client)

    with pytest.raises(RateLimitExceededError) as refused:
        await limiter.check_rate_limit(key=key, limit=limit, window_seconds=86400)

    assert abs(refused.value.details["retry_after"] - wait) <= 2
