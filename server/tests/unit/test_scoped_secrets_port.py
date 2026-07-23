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
async def test_scoped_port_resolves_same_workspace_secret_by_opaque_id(db, ctx):
    secret = Secret(
        id="sec_same_workspace",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="Runtime credential",
        secret_ref="secret:sec_same_workspace",
    )
    db.add(secret)
    db.commit()
    store = RecordingSecretValueStore()

    value = await ScopedSecretsPort(ctx=ctx, value_store=store, db=db).get_secret(
        secret_id=secret.id
    )

    assert value == "resolved-value"
    store.get_secret_value_mock.assert_awaited_once_with(
        locator=SecretLocator("secret:sec_same_workspace")
    )


@pytest.mark.asyncio
async def test_scoped_port_rejects_cross_workspace_secret_without_touching_store(db, ctx):
    db.add(
        Secret(
            id="sec_other_workspace",
            tenant_id=ctx.tenant_id,
            workspace_id="other-workspace",
            name="Other credential",
            secret_ref="secret:sec_other_workspace",
        )
    )
    db.commit()
    store = RecordingSecretValueStore()

    with pytest.raises(NotFoundError, match="Secret not found") as exc_info:
        await ScopedSecretsPort(ctx=ctx, value_store=store, db=db).get_secret(
            secret_id="sec_other_workspace"
        )

    assert exc_info.value.message == "Secret not found"
    store.get_secret_value_mock.assert_not_awaited()
    audit = db.exec(
        select(AuditEvent).where(
            AuditEvent.event_type == "security.secret.access_denied"
        )
    ).one()
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
async def test_scoped_port_rejects_raw_locator_input_immediately(db, ctx, unsafe_value):
    store = RecordingSecretValueStore()

    with pytest.raises(ValidationError, match="opaque secret_id"):
        await ScopedSecretsPort(ctx=ctx, value_store=store, db=db).get_secret(
            secret_id=unsafe_value
        )

    store.get_secret_value_mock.assert_not_awaited()
    audit = db.exec(
        select(AuditEvent).where(
            AuditEvent.event_type == "security.secret.access_denied"
        )
    ).one()
    assert audit.resource_id is None
    assert unsafe_value not in str(audit.payload_json)


def test_secret_api_response_does_not_expose_internal_locator():
    assert "secret_ref" not in SecretResponse.model_fields
