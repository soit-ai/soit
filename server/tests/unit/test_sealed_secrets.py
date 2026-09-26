"""The sealed secrets backend keeps values across restarts, sealed at rest."""

from __future__ import annotations

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.adapters.secrets.sealed import SealedDatabaseSecretValueStore
from app.kernel.commons.errors import KernelError
from app.kernel.ports.secrets.interface import SecretLocator
from app.kernel.runtime.db.models.secrets import SealedSecretValue
from app.settings.settings import Settings
from tests.unit.test_content_safety_port import _production_settings

KEY = "an-evaluation-secret-key-of-enough-length"


def _store(async_db: AsyncSession, secret_key: str = KEY) -> SealedDatabaseSecretValueStore:
    engine = async_db.bind
    return SealedDatabaseSecretValueStore(
        lambda: AsyncSession(engine, expire_on_commit=False), secret_key=secret_key
    )


@pytest.mark.asyncio
async def test_values_round_trip_and_survive_a_new_store(async_db) -> None:
    locator = SecretLocator("secret:ws_1:openai")
    await _store(async_db).set_secret_value(locator, "sk-live-value")

    # A new store instance stands in for a restarted process.
    assert await _store(async_db).get_secret_value(locator) == "sk-live-value"


@pytest.mark.asyncio
async def test_values_are_sealed_at_rest(async_db) -> None:
    locator = SecretLocator("secret:ws_1:deepseek")
    await _store(async_db).set_secret_value(locator, "plain-text-value")

    async with AsyncSession(async_db.bind) as db:
        row = await db.get(SealedSecretValue, locator.value)
    assert row is not None
    assert "plain-text-value" not in row.sealed_value


@pytest.mark.asyncio
async def test_overwrite_delete_and_missing(async_db) -> None:
    store = _store(async_db)
    locator = SecretLocator("secret:ws_1:rotating")
    await store.set_secret_value(locator, "first")
    await store.set_secret_value(locator, "second")
    assert await store.get_secret_value(locator) == "second"

    await store.delete_secret_value(locator)
    assert await store.get_secret_value(locator) == ""
    assert await store.get_secret_value(SecretLocator("secret:never:written")) == ""


@pytest.mark.asyncio
async def test_a_changed_secret_key_fails_loudly(async_db) -> None:
    locator = SecretLocator("secret:ws_1:orphaned")
    await _store(async_db).set_secret_value(locator, "value")

    with pytest.raises(KernelError) as raised:
        await _store(async_db, secret_key="a-different-secret-key-entirely-1234").get_secret_value(
            locator
        )
    assert raised.value.code == "SEALED_VALUE_UNREADABLE"


def test_the_backend_setting_is_validated() -> None:
    assert Settings(_env_file=None, secrets_backend=" Sealed ").secrets_backend == "sealed"
    with pytest.raises(ValueError):
        Settings(_env_file=None, secrets_backend="file")


def test_production_refuses_the_sealed_backend() -> None:
    production = _production_settings(secrets_backend="sealed")
    with pytest.raises(ValueError, match="Vault secrets backend"):
        production.validate_runtime_requirements()
    _production_settings(secrets_backend="vault").validate_runtime_requirements()


def test_the_container_selects_the_sealed_store(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.settings.settings import settings
    from app.wiring.container import Container

    monkeypatch.setattr(Container, "_is_explicit_test_runtime", staticmethod(lambda: False))
    monkeypatch.setattr(settings, "secrets_backend", "sealed")
    monkeypatch.setattr(settings, "environment", "local")

    store = Container()._create_secrets_port()

    assert isinstance(store, SealedDatabaseSecretValueStore)
