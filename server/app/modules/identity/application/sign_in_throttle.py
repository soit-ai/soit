"""Failed sign-in counting, so passwords and second factors cannot be guessed.

Each failure increments a counter in Redis that expires a fixed window after
the first failure. Once a subject reaches the limit, further attempts are
refused until the window ends, whether or not they would have succeeded:
otherwise the refusal would only slow the guessing, not stop it. A success
clears the counter.

Subjects are an account's email (password sign-in, reset mail) or a user id
(second factor), never a client address: behind the bundled reverse proxy
every request comes from the proxy, and one counter for everyone would let a
single client lock every account out.

Redis being unreachable lets attempts through with a warning, as the other
limiters do: refusing every sign-in would turn a cache outage into an outage
of the whole product.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Protocol

from app.kernel.commons.errors import RateLimitExceededError

logger = logging.getLogger(__name__)


class _CounterStore(Protocol):
    async def get(self, name: str) -> Any: ...

    async def incr(self, name: str) -> int: ...

    async def expire(self, name: str, time: int) -> Any: ...

    async def ttl(self, name: str) -> int: ...

    async def delete(self, *names: str) -> Any: ...


class SignInThrottle:
    """Count failures per subject and refuse once a subject has too many."""

    def __init__(
        self,
        store: _CounterStore | None = None,
        *,
        max_failures: int,
        window_seconds: int,
    ) -> None:
        self._store = store
        self.max_failures = max(1, max_failures)
        self.window_seconds = max(1, window_seconds)

    def _redis(self) -> _CounterStore:
        if self._store is not None:
            return self._store
        from app.kernel.ports.common.redis_client import shared_redis

        return shared_redis()

    @staticmethod
    def _key(scope: str, subject: str) -> str:
        # Hashed so an email address never sits in Redis in the clear.
        digest = hashlib.sha256(subject.strip().lower().encode("utf-8")).hexdigest()
        return f"signin:failures:{scope}:{digest}"

    async def ensure_allowed(self, scope: str, subject: str) -> None:
        """Raise RateLimitExceededError while ``subject`` is locked out."""
        key = self._key(scope, subject)
        try:
            store = self._redis()
            raw = await store.get(key)
            if raw is None or int(raw) < self.max_failures:
                return
            ttl = await store.ttl(key)
        except Exception as exc:  # noqa: BLE001 — fail open, see module docstring
            logger.warning("Sign-in throttle unavailable (allowing attempt): %s", exc)
            return
        retry_after = ttl if isinstance(ttl, int) and ttl > 0 else self.window_seconds
        raise RateLimitExceededError(
            "Too many failed attempts. Try again later.",
            {"retry_after": retry_after, "scope": scope},
        )

    async def record_failure(self, scope: str, subject: str) -> None:
        key = self._key(scope, subject)
        try:
            store = self._redis()
            count = await store.incr(key)
            if int(count) == 1:
                await store.expire(key, self.window_seconds)
        except Exception as exc:  # noqa: BLE001 — fail open, see module docstring
            logger.warning("Sign-in throttle unavailable (failure not counted): %s", exc)

    async def reset(self, scope: str, subject: str) -> None:
        try:
            await self._redis().delete(self._key(scope, subject))
        except Exception as exc:  # noqa: BLE001 — fail open, see module docstring
            logger.warning("Sign-in throttle unavailable (counter not cleared): %s", exc)
