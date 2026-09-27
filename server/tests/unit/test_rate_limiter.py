""" test_rate_limiter

Unit tests for rate limiter.
"""

import time
from unittest.mock import AsyncMock

import pytest
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
