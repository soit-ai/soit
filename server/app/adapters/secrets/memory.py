"""memory

In-memory secrets adapter for tests.
"""

from __future__ import annotations

from typing import Any

from app.kernel.ports.secrets.interface import SecretsPort


class InMemorySecretsPort(SecretsPort):
    """In-memory secrets storage."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get_secret(self, secret_ref: str, **kwargs: Any) -> str:
        return self._store.get(secret_ref, "")

    async def set_secret(self, secret_ref: str, value: str, **kwargs: Any) -> None:
        self._store[secret_ref] = value

    async def delete_secret(self, secret_ref: str, **kwargs: Any) -> None:
        self._store.pop(secret_ref, None)
