"""Scoped secret resolution contract tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlmodel import select

from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.ports.secrets.interface import SecretLocator, SecretValueStore
from app.kernel.runtime.db.models.audit import AuditEvent
from app.modules.secrets.application.schemas import SecretResponse
from app.modules.secrets.domain.models import Secret
from app.modules.secrets.infra.scoped_port import ScopedSecretsPort


class RecordingSecretValueStore(SecretValueStore):
    """Record trusted-store calls without retaining plaintext values."""

    def __init__(self) -> None:
        self.get_secret_value_mock = AsyncMock(return_value="resolved-value")
        self.set_secret_value_mock = AsyncMock()
        self.delete_secret_value_mock = AsyncMock()

    async def get_secret_value(self, locator, **kwargs):
        return await self.get_secret_value_mock(locator=locator, **kwargs)

    async def set_secret_value(self, locator, value, **kwargs):
        await self.set_secret_value_mock(locator=locator, value=value, **kwargs)

    async def delete_secret_value(self, locator, **kwargs):
        await self.delete_secret_value_mock(locator=locator, **kwargs)


@pytest.mark.asyncio
async def test_scoped_port_resolves_same_workspace_secret_by_opaque_id(async_db, ctx):
    secret = Secret(
        id="sec_same_workspace",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="Runtime credential",
        secret_ref="secret:sec_same_workspace",
    )
    async_db.add(secret)
    await async_db.commit()
    store = RecordingSecretValueStore()

    value = await ScopedSecretsPort(ctx=ctx, value_store=store, db=async_db).get_secret(
        secret_id=secret.id
    )

    assert value == "resolved-value"
    store.get_secret_value_mock.assert_awaited_once_with(
        locator=SecretLocator("secret:sec_same_workspace")
    )


@pytest.mark.asyncio
async def test_scoped_port_rejects_cross_workspace_secret_without_touching_store(async_db, ctx):
    async_db.add(
        Secret(
            id="sec_other_workspace",
            tenant_id=ctx.tenant_id,
            workspace_id="other-workspace",
            name="Other credential",
            secret_ref="secret:sec_other_workspace",
        )
    )
    await async_db.commit()
    store = RecordingSecretValueStore()

    with pytest.raises(NotFoundError, match="Secret not found") as exc_info:
        await ScopedSecretsPort(ctx=ctx, value_store=store, db=async_db).get_secret(
            secret_id="sec_other_workspace"
        )

    assert exc_info.value.message == "Secret not found"
    store.get_secret_value_mock.assert_not_awaited()
    audit = (await async_db.exec(
        select(AuditEvent).where(
            AuditEvent.event_type == "security.secret.access_denied"
        )
    )).one()
    assert audit.resource_id == "sec_other_workspace"
    assert audit.outcome == "denied"
    assert "secret_ref" not in audit.payload_json
    assert "locator" not in audit.payload_json


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unsafe_value",
    [
        "secret:sec_same_workspace",
        "kv/team/provider",
        "sec_same_workspace:value",
    ],
)
async def test_scoped_port_rejects_raw_locator_input_immediately(async_db, ctx, unsafe_value):
    store = RecordingSecretValueStore()

    with pytest.raises(ValidationError, match="opaque secret_id"):
        await ScopedSecretsPort(ctx=ctx, value_store=store, db=async_db).get_secret(
            secret_id=unsafe_value
        )

    store.get_secret_value_mock.assert_not_awaited()
    audit = (await async_db.exec(
        select(AuditEvent).where(
            AuditEvent.event_type == "security.secret.access_denied"
        )
    )).one()
    assert audit.resource_id is None
    assert unsafe_value not in str(audit.payload_json)


def test_secret_api_response_does_not_expose_internal_locator():
    assert "secret_ref" not in SecretResponse.model_fields


async def _seed_secret(async_db, ctx, secret_id: str) -> Secret:
    secret = Secret(
        id=secret_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name=f"Credential {secret_id}",
        secret_ref=f"secret:{secret_id}",
    )
    async_db.add(secret)
    await async_db.commit()
    return secret


async def _resolution_count(async_db, secret_id: str) -> int:
    rows = (await async_db.exec(
        select(AuditEvent).where(
            AuditEvent.resource_id == secret_id,
            AuditEvent.outcome == "allowed",
        )
    )).all()
    return len(rows)


@pytest.mark.asyncio
async def test_a_repeated_resolution_reuses_the_value_and_is_still_audited(async_db, ctx):
    secret = await _seed_secret(async_db, ctx, "sec_cached")
    store = RecordingSecretValueStore()
    port = ScopedSecretsPort(ctx=ctx, value_store=store, db=async_db)

    assert await port.get_secret(secret_id=secret.id) == "resolved-value"
    assert await port.get_secret(secret_id=secret.id) == "resolved-value"

    store.get_secret_value_mock.assert_awaited_once()
    assert await _resolution_count(async_db, secret.id) == 2


@pytest.mark.asyncio
async def test_rotating_a_secret_skips_the_cached_value(async_db, ctx):
    from datetime import timedelta

    secret = await _seed_secret(async_db, ctx, "sec_rotated")
    store = RecordingSecretValueStore()
    port = ScopedSecretsPort(ctx=ctx, value_store=store, db=async_db)
    await port.get_secret(secret_id=secret.id)

    store.get_secret_value_mock.return_value = "rotated-value"
    secret.last_rotated_at = secret.updated_at + timedelta(seconds=1)
    secret.updated_at = secret.last_rotated_at
    async_db.add(secret)
    await async_db.commit()

    assert await port.get_secret(secret_id=secret.id) == "rotated-value"
    assert store.get_secret_value_mock.await_count == 2


@pytest.mark.asyncio
async def test_a_zero_ttl_reads_the_store_every_time(async_db, ctx, monkeypatch):
    from app.modules.secrets.infra import scoped_port

    monkeypatch.setattr(scoped_port.settings, "secret_value_cache_seconds", 0)
    secret = await _seed_secret(async_db, ctx, "sec_uncached")
    store = RecordingSecretValueStore()
    port = ScopedSecretsPort(ctx=ctx, value_store=store, db=async_db)

    await port.get_secret(secret_id=secret.id)
    await port.get_secret(secret_id=secret.id)

    assert store.get_secret_value_mock.await_count == 2
