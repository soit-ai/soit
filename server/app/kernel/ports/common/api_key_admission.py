""" api_key_admission

What one API key may still spend, counted the same whichever door a call uses.

A key's rate and daily request quota are one budget: a model call through the
gateway and a tool call through the tool API or MCP spend the same counters,
so a key limited to 60 calls a minute makes 60 calls a minute, not 60 of each
kind. The token quota is the model gateway's alone, since only model calls use
tokens.

The two request limits are spent separately because a tool call can be sent
more than once. The per-minute rate throttles requests, so every request spends
it, a poll or replay included; the daily quota counts calls, so a call spends
it once, when it starts.
"""

from __future__ import annotations

from app.kernel.commons.errors import RateLimitExceededError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.common.rate_limiter import RateLimiter
from app.kernel.ports.common.usage_counter import (
    DailyUsageCounter,
    seconds_until_next_utc_day,
)

# The names predate tool calls sharing them; renaming would reset every key's
# windows on the day it deployed.
_RATE_COUNTER = "llm:api_key:{key_id}"
_DAILY_REQUEST_COUNTER = "quota:llm:api_key:{key_id}"
_DAILY_TOKEN_COUNTER = "tokens:api_key:{key_id}"


class ApiKeyAdmission:
    """Spend and check the limits of the key that authenticated ``ctx``.

    A context no key authenticated spends nothing: a member's session is held
    by the member's own limits.
    """

    def __init__(
        self,
        ctx: RequestContext,
        *,
        rate_limiter: RateLimiter | None = None,
        usage_counter: DailyUsageCounter | None = None,
    ) -> None:
        self.ctx = ctx
        self.rate_limiter = rate_limiter or RateLimiter()
        self.usage_counter = usage_counter or DailyUsageCounter()

    async def admit_rate(self) -> None:
        """Spend one request of the key's per-minute rate."""
        key_id = self.ctx.api_key_id
        limit = self.ctx.api_key_rate_limit_per_minute
        if key_id is None or not limit:
            return
        await self._spend(_RATE_COUNTER.format(key_id=key_id), limit, 60, quota="per_minute")

    async def admit_daily_request(self) -> None:
        """Spend one call of the key's rolling 24-hour request quota."""
        key_id = self.ctx.api_key_id
        limit = self.ctx.api_key_daily_request_quota
        if key_id is None or not limit:
            return
        await self._spend(
            _DAILY_REQUEST_COUNTER.format(key_id=key_id), limit, 86400, quota="daily_requests"
        )

    async def admit_request(self) -> None:
        """Spend both request limits, for a call that is made once."""
        await self.admit_rate()
        await self.admit_daily_request()

    async def check_tokens(self) -> None:
        """Refuse a model call once the key's daily token quota is used up."""
        counter = self._token_counter()
        quota = self.ctx.api_key_daily_token_quota
        if counter is None or not quota:
            return
        now = utc_now()
        used = await self.usage_counter.total(counter, now=now)
        if used >= quota:
            raise RateLimitExceededError(
                "API key daily token quota exhausted",
                {
                    "limit": quota,
                    "used": used,
                    "quota": "daily_tokens",
                    "retry_after": seconds_until_next_utc_day(now),
                },
            )

    async def count_tokens(self, tokens: int) -> None:
        """Add what a finished model call used to its key's daily token total."""
        counter = self._token_counter()
        if counter is not None and tokens > 0:
            await self.usage_counter.add(counter, tokens)

    def _token_counter(self) -> str | None:
        if self.ctx.api_key_id is None or not self.ctx.api_key_daily_token_quota:
            return None
        return _DAILY_TOKEN_COUNTER.format(key_id=self.ctx.api_key_id)

    async def _spend(self, counter: str, limit: int, window_seconds: int, *, quota: str) -> None:
        try:
            await self.rate_limiter.check_rate_limit(
                key=counter, limit=limit, window_seconds=window_seconds
            )
        except RateLimitExceededError as exc:
            # Which of the key's limits refused, so a caller can tell a
            # minute's wait from a day's.
            raise RateLimitExceededError(exc.message, {**(exc.details or {}), "quota": quota}) from None
