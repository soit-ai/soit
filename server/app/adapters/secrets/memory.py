"""memory

In-memory secrets adapter for tests.
"""

from __future__ import annotations

from typing import Any

from app.kernel.ports.secrets.interface import SecretLocator, SecretValueStore


class InMemorySecretValueStore(SecretValueStore):
    """In-memory secrets storage."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get_secret_value(self, locator: SecretLocator, **kwargs: Any) -> str:
        return self._store.get(locator.value, "")

    async def set_secret_value(
        self, locator: SecretLocator, value: str, **kwargs: Any
    ) -> None:
        self._store[locator.value] = value

    async def delete_secret_value(self, locator: SecretLocator, **kwargs: Any) -> None:
        self._store.pop(locator.value, None)
