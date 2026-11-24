"""SignInThrottle: counts failures per subject and fails open without Redis."""

from __future__ import annotations

import pytest

from app.kernel.commons.errors import RateLimitExceededError
from app.modules.identity.application.sign_in_throttle import SignInThrottle


class Counters:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expiries: dict[str, int] = {}

    async def get(self, name):
        return self.values.get(name)

    async def incr(self, name):
        self.values[name] = self.values.get(name, 0) + 1
        return self.values[name]

    async def expire(self, name, time):
        self.expiries[name] = time
        return True

    async def ttl(self, name):
        return 17

    async def delete(self, *names):
        for name in names:
            self.values.pop(name, None)
        return 1


class Unreachable:
    async def _fail(self, *args, **kwargs):
        raise ConnectionError("redis down")

    get = incr = expire = ttl = delete = _fail


@pytest.mark.asyncio
async def test_refuses_once_the_limit_is_reached_and_reports_the_wait() -> None:
    store = Counters()
    throttle = SignInThrottle(store, max_failures=2, window_seconds=900)

    await throttle.ensure_allowed("password", "a@example.com")
    await throttle.record_failure("password", "a@example.com")
    await throttle.ensure_allowed("password", "a@example.com")
    await throttle.record_failure("password", "a@example.com")

    with pytest.raises(RateLimitExceededError) as refused:
        await throttle.ensure_allowed("password", "a@example.com")
    assert refused.value.details["retry_after"] == 17
    # The window starts at the first failure and is not pushed back by later ones.
    assert list(store.expiries.values()) == [900]


@pytest.mark.asyncio
async def test_subjects_and_scopes_are_counted_apart_and_case_folded() -> None:
    store = Counters()
    throttle = SignInThrottle(store, max_failures=1, window_seconds=60)

    await throttle.record_failure("password", "A@Example.com")
    with pytest.raises(RateLimitExceededError):
        await throttle.ensure_allowed("password", "a@example.com")
    await throttle.ensure_allowed("password", "b@example.com")
    await throttle.ensure_allowed("second_factor", "a@example.com")
    assert not any("example.com" in key for key in store.values)


@pytest.mark.asyncio
async def test_reset_clears_the_count() -> None:
    store = Counters()
    throttle = SignInThrottle(store, max_failures=1, window_seconds=60)
    await throttle.record_failure("password", "a@example.com")
    await throttle.reset("password", "a@example.com")
    await throttle.ensure_allowed("password", "a@example.com")


@pytest.mark.asyncio
async def test_an_unreachable_store_lets_attempts_through() -> None:
    throttle = SignInThrottle(Unreachable(), max_failures=1, window_seconds=60)
    await throttle.record_failure("password", "a@example.com")
    await throttle.ensure_allowed("password", "a@example.com")
    await throttle.reset("password", "a@example.com")
