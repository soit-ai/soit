"""Apprise outbound delivery consumer."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from apprise import Apprise
from sqlalchemy.orm import Session

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.secrets.interface import SecretsPort
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.security.egress import GovernedEgressGuard
from app.modules.notification.domain.models import (
    Notification,
    NotificationDelivery,
    NotificationEndpoint,
)

AppriseSender = Callable[..., Awaitable[bool]]


async def _send_apprise(url: str, *, title: str, body: str) -> bool:
    def send() -> bool:
        notifier = Apprise()
        if not notifier.add(url):
            return False
        return bool(notifier.notify(title=title, body=body))

    return await asyncio.to_thread(send)


async def handle_notification_delivery_outbox(
    db: Session,
    row: EventOutbox | Any,
    *,
    secrets_port: SecretsPort | None = None,
    sender: AppriseSender | None = None,
    egress_guard: GovernedEgressGuard | None = None,
) -> None:
    """Deliver one queued notification without exposing its endpoint URL."""
    delivery_id = str((row.payload_json or {}).get("delivery_id") or "")
    delivery = db.get(NotificationDelivery, delivery_id)
    if delivery is None or delivery.status in {"sent", "failed"}:
        return
    endpoint = db.get(NotificationEndpoint, delivery.endpoint_id)
    notification = db.get(Notification, delivery.notification_id)
    if endpoint is None or notification is None:
        delivery.status = "failed"
        delivery.last_error = "ReferenceNotFound"
        delivery.updated_at = utc_now()
        db.add(delivery)
        db.flush()
        return
    if (
        endpoint.tenant_id != delivery.tenant_id
        or endpoint.workspace_id != delivery.workspace_id
        or notification.tenant_id != delivery.tenant_id
        or notification.workspace_id != delivery.workspace_id
    ):
        delivery.status = "failed"
        delivery.last_error = "ScopeMismatch"
        delivery.updated_at = utc_now()
        db.add(delivery)
        db.flush()
        return
    if endpoint.status != "active":
        delivery.status = "failed"
        delivery.last_error = "EndpointDisabled"
        delivery.updated_at = utc_now()
        db.add(delivery)
        db.flush()
        return

    delivery.status = "sending"
    delivery.attempt_count = int(delivery.attempt_count or 0) + 1
    delivery.updated_at = utc_now()
    db.add(delivery)
    try:
        if secrets_port is None:
            raise RuntimeError("Scoped secrets port is unavailable")
        url = await secrets_port.get_secret(secret_id=endpoint.secret_id)
        ctx = RequestContext(
            tenant_id=delivery.tenant_id,
            workspace_id=delivery.workspace_id,
            user_id="system:notification-delivery",
            request_id=str(getattr(row, "id", "") or delivery.id),
        )
        await (egress_guard or GovernedEgressGuard()).authorize(
            ctx,
            f"notification:endpoint:{endpoint.id}",
            url,
            allow_non_http=True,
        )
        delivered = await (sender or _send_apprise)(
            url,
            title=notification.title,
            body=notification.content or "",
        )
        if not delivered:
            raise RuntimeError("Apprise provider rejected the notification")
    except Exception as exc:
        delivery.last_error = type(exc).__name__
        delivery.updated_at = utc_now()
        if delivery.attempt_count >= 5:
            delivery.status = "failed"
            db.add(delivery)
            db.flush()
            return
        delivery.status = "queued"
        db.add(delivery)
        db.flush()
        raise RuntimeError("notification delivery failed") from None

    delivery.status = "sent"
    delivery.last_error = None
    delivery.sent_at = utc_now()
    delivery.updated_at = delivery.sent_at
    db.add(delivery)
    db.flush()
