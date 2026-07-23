"""Tests for Apprise outbox delivery behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.notification.domain.models import (
    Notification,
    NotificationDelivery,
    NotificationEndpoint,
)
from app.modules.notification.handlers.apprise_delivery import (
    handle_notification_delivery_outbox,
)
from app.modules.secrets.domain.models import Secret


class AllowEgressGuard:
    async def authorize(self, *args, **kwargs) -> None:
        return None


def _seed_delivery(db, ctx):
    notification = Notification(
        id="ntf_delivery_test",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        type="system",
        title="Delivery title",
        content="Delivery body",
    )
    secret = Secret(
        id="sec_notification_endpoint_test",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="Notification endpoint",
        secret_ref="secret:sec_notification_endpoint_test",
    )
    endpoint = NotificationEndpoint(
        id="nep_delivery_test",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        name="Test endpoint",
        kind="email",
        secret_id=secret.id,
        display_target="mailto://***@example.com",
    )
    delivery = NotificationDelivery(
        id="ndel_delivery_test",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        notification_id=notification.id,
        endpoint_id=endpoint.id,
    )
    db.add_all([notification, secret, endpoint, delivery])
    db.commit()
    return delivery


@pytest.mark.asyncio
async def test_apprise_handler_resolves_secret_and_marks_delivery_sent(db, ctx):
    delivery = _seed_delivery(db, ctx)
    secrets = SimpleNamespace(get_secret=AsyncMock(return_value="mailto://user:password@example.com"))
    sender = AsyncMock(return_value=True)
    row = SimpleNamespace(payload_json={"delivery_id": delivery.id})

    await handle_notification_delivery_outbox(
        db,
        row,
        secrets_port=secrets,
        sender=sender,
        egress_guard=AllowEgressGuard(),
    )

    db.refresh(delivery)
    assert delivery.status == "sent"
    assert delivery.attempt_count == 1
    secrets.get_secret.assert_awaited_once_with(secret_id="sec_notification_endpoint_test")
    sender.assert_awaited_once_with(
        "mailto://user:password@example.com",
        title="Delivery title",
        body="Delivery body",
    )


@pytest.mark.asyncio
async def test_apprise_handler_stops_after_five_attempts(db, ctx):
    delivery = _seed_delivery(db, ctx)
    secrets = SimpleNamespace(get_secret=AsyncMock(return_value="json://example.com"))
    sender = AsyncMock(side_effect=RuntimeError("provider failed"))
    row = SimpleNamespace(payload_json={"delivery_id": delivery.id})

    for _ in range(4):
        with pytest.raises(RuntimeError, match="notification delivery failed"):
            await handle_notification_delivery_outbox(
                db,
                row,
                secrets_port=secrets,
                sender=sender,
                egress_guard=AllowEgressGuard(),
            )
    await handle_notification_delivery_outbox(
        db,
        row,
        secrets_port=secrets,
        sender=sender,
        egress_guard=AllowEgressGuard(),
    )

    db.refresh(delivery)
    assert delivery.status == "failed"
    assert delivery.attempt_count == 5
    assert delivery.last_error == "RuntimeError"
