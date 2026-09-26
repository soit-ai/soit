"""Secret values sealed in the application database.

For evaluation installs that run without Vault: values survive restarts,
unlike the in-memory store, and sit in ``sealed_secret_values`` encrypted with
a key derived from ``SECRET_KEY``. Anyone holding both a database dump and the
application secret can open them, so production keeps secrets in Vault; the
settings refuse this backend in production.

Each call uses its own session and commits on its own, the way a call to
Vault would: the value store is independent of the caller's transaction.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import delete
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.identity.sealing import seal, unseal
from app.kernel.ports.secrets.interface import SecretLocator, SecretValueStore
from app.kernel.runtime.db.models.secrets import SealedSecretValue
from app.settings.settings import settings


def _default_session_factory() -> AsyncSession:
    from app.infra.db.session import get_async_session_local

    return get_async_session_local()()


class SealedDatabaseSecretValueStore(SecretValueStore):
    """Secret values sealed at rest in the application database."""

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession] | None = None,
        *,
        secret_key: str | None = None,
    ) -> None:
        self._session_factory = session_factory or _default_session_factory
        self._secret_key = secret_key if secret_key is not None else settings.secret_key

    async def get_secret_value(self, locator: SecretLocator, **kwargs: Any) -> str:
        async with self._session_factory() as db:
            row = await db.get(SealedSecretValue, locator.value)
            if row is None:
                return ""
            return unseal(row.sealed_value, secret_key=self._secret_key)

    async def set_secret_value(
        self, locator: SecretLocator, value: str, **kwargs: Any
    ) -> None:
        sealed = seal(value, secret_key=self._secret_key)
        async with self._session_factory() as db:
            row = await db.get(SealedSecretValue, locator.value)
            now = utc_now()
            if row is None:
                row = SealedSecretValue(
                    locator=locator.value, sealed_value=sealed, created_at=now, updated_at=now
                )
            else:
                row.sealed_value = sealed
                row.updated_at = now
            db.add(row)
            await db.commit()

    async def delete_secret_value(self, locator: SecretLocator, **kwargs: Any) -> None:
        async with self._session_factory() as db:
            await db.exec(
                delete(SealedSecretValue).where(SealedSecretValue.locator == locator.value)
            )
            await db.commit()
