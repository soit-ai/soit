""" test_rate_limiter

Unit tests for rate limiter.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import redis.asyncio as redis_async

from app.kernel.gateways.common.rate_limiter import RateLimiter
from app.kernel.commons.errors import ForbiddenError


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis_client = AsyncMock(spec=redis_async.Redis)
    redis_client.eval = AsyncMock(return_value=1)  # Allowed
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
    """Test that exceeding rate limit raises ForbiddenError."""
    # Mock Redis to return 0 (rate limit exceeded)
    mock_redis.eval = AsyncMock(return_value=0)
    
    limiter = RateLimiter(redis_client=mock_redis)
    
    with pytest.raises(ForbiddenError):
        await limiter.check_rate_limit(
            key="test_key",
            limit=10,
            window_seconds=60,
        )


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

