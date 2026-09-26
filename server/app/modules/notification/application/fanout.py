""" fanout

How a notification leaves the inbox: one place for the preference check and
the delivery staging that every alert shares.

A member's notification goes to their inbox when they keep its category on,
and to their own endpoints when their delivery mode says so, deferred past
their quiet hours. A workspace alert also goes to the workspace endpoints
subscribed to its category: team channels and webhooks that someone on call
reads, which do not depend on any one member's settings.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.ids import generate_notification_id, generate_ulid
from app.kernel.commons.time import utc_now
from app.kernel.contracts.notification import NOTIFICATION_STATUS_UNREAD
from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.publisher import OutboxPublisher
from app.modules.identity.domain.models import WorkspaceMembership
from app.modules.notification.domain.models import (
    Notification,
    NotificationDelivery,
    NotificationEndpoint,
    NotificationPreference,
)

DEFAULT_WORKSPACE_CATEGORIES = ("alert",)
"""What a workspace endpoint receives when it names no categories."""

WORKSPACE_RECIPIENT_PREFIX = "workspace:"
"""Recipient of the notification a workspace endpoint delivers; no one's inbox."""


def stage_delivery(
    db: AsyncSession,
    notification: Notification,
    endpoint: NotificationEndpoint,
    available_at: datetime,
) -> NotificationDelivery:
    """Queue one delivery and the outbox event that sends it."""
    now = utc_now()
    delivery = NotificationDelivery(
        tenant_id=notification.tenant_id,
        workspace_id=notification.workspace_id,
        user_id=notification.user_id,
        notification_id=notification.id,
        endpoint_id=endpoint.id,
        status="queued",
        available_at=available_at,
        created_at=now,
        updated_at=now,
    )
    db.add(delivery)
    OutboxPublisher(OutboxRepository(db)).publish(
        DomainEventEnvelope(
            event_id=f"evt_{generate_ulid()}",
            event_type="notification.delivery.requested",
            tenant_id=notification.tenant_id,
            workspace_id=notification.workspace_id,
            idempotency_key=delivery.id,
            subject_type="notification_delivery",
            subject_id=delivery.id,
            producer="notification",
            occurred_at=now,
            payload={"delivery_id": delivery.id},
        ),
        available_at=available_at,
    )
    return delivery


def next_delivery_time(preference: NotificationPreference, now: datetime) -> datetime:
    """``now``, or the end of the member's quiet hours when ``now`` falls in them."""
    if not preference.quiet_hours_enabled:
        return now
    try:
        zone = ZoneInfo(preference.timezone)
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("UTC")
    local_now = now.astimezone(zone)
    start = time.fromisoformat(preference.quiet_hours_start)
    end = time.fromisoformat(preference.quiet_hours_end)
    local_time = local_now.time().replace(tzinfo=None)
    in_quiet = start <= local_time < end if start < end else local_time >= start or local_time < end
    if not in_quiet:
        return now
    end_date = local_now.date()
    if start >= end and local_time >= start:
        end_date += timedelta(days=1)
    return datetime.combine(end_date, end, tzinfo=zone).astimezone(UTC)


async def _preference(
    db: AsyncSession, tenant_id: str, workspace_id: str, user_id: str
) -> NotificationPreference | None:
    query = select(NotificationPreference).where(
        and_(
            NotificationPreference.tenant_id == tenant_id,
            NotificationPreference.workspace_id == workspace_id,
            NotificationPreference.user_id == user_id,
        )
    )
    return (await db.exec(query)).scalars().first()


def _category_enabled(preference: NotificationPreference | None, category: str) -> bool:
    # Security notices cannot be switched off; everything else defaults on.
    if preference is None or category == "security":
        return True
    return bool((preference.categories_json or {}).get(category, True))


async def wants_category(
    db: AsyncSession, tenant_id: str, workspace_id: str, user_id: str, category: str
) -> bool:
    """Whether a member keeps notifications of ``category`` on."""
    return _category_enabled(await _preference(db, tenant_id, workspace_id, user_id), category)


async def stage_member_deliveries(
    db: AsyncSession, notification: Notification, category: str
) -> list[NotificationDelivery]:
    """Send a member's notification to their own endpoints, as they asked."""
    preference = await _preference(
        db, notification.tenant_id, notification.workspace_id, notification.user_id
    )
    if preference is None or preference.delivery_mode == "in_app":
        return []
    if not _category_enabled(preference, category):
        return []
    query = select(NotificationEndpoint).where(
        and_(
            NotificationEndpoint.tenant_id == notification.tenant_id,
            NotificationEndpoint.workspace_id == notification.workspace_id,
            NotificationEndpoint.user_id == notification.user_id,
            NotificationEndpoint.scope == "user",
            NotificationEndpoint.status == "active",
        )
    )
    endpoints = list((await db.exec(query)).scalars())
    if preference.delivery_mode == "in_app_email":
        endpoints = [endpoint for endpoint in endpoints if endpoint.kind == "email"]
    available_at = next_delivery_time(preference, utc_now())
    return [stage_delivery(db, notification, endpoint, available_at) for endpoint in endpoints]


async def members_with_roles(
    db: AsyncSession, tenant_id: str, workspace_id: str, roles: Sequence[str]
) -> list[str]:
    query = select(WorkspaceMembership.user_id).where(
        and_(
            WorkspaceMembership.tenant_id == tenant_id,
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.role.in_(list(roles)),
        )
    )
    return [str(user_id) for user_id in (await db.exec(query)).scalars()]


def _notification(
    *,
    tenant_id: str,
    workspace_id: str,
    user_id: str,
    title: str,
    content: str | None,
    severity: str,
    source_module: str,
    action: dict[str, Any] | None,
    meta: dict[str, Any] | None,
) -> Notification:
    now = utc_now()
    return Notification(
        id=generate_notification_id(),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_id=user_id,
        type="alert",
        severity=severity,
        status=NOTIFICATION_STATUS_UNREAD,
        title=title,
        content=content,
        source_module=source_module,
        action=action,
        meta=meta,
        created_at=now,
        updated_at=now,
    )


async def notify_members(
    db: AsyncSession,
    *,
    tenant_id: str,
    workspace_id: str,
    roles: Sequence[str],
    category: str,
    title: str,
    content: str | None,
    severity: str,
    source_module: str,
    action: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> list[Notification]:
    """Notify the members holding ``roles`` who keep ``category`` on."""
    created: list[Notification] = []
    for user_id in await members_with_roles(db, tenant_id, workspace_id, roles):
        if not await wants_category(db, tenant_id, workspace_id, user_id, category):
            continue
        notification = _notification(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
            content=content,
            severity=severity,
            source_module=source_module,
            action=action,
            meta={**(meta or {}), "category": category},
        )
        db.add(notification)
        await stage_member_deliveries(db, notification, category)
        created.append(notification)
    return created


async def notify_workspace_endpoints(
    db: AsyncSession,
    *,
    tenant_id: str,
    workspace_id: str,
    category: str,
    title: str,
    content: str | None,
    severity: str,
    source_module: str,
    meta: dict[str, Any] | None = None,
) -> list[NotificationDelivery]:
    """Send a workspace alert to the workspace endpoints subscribed to it."""
    query = select(NotificationEndpoint).where(
        and_(
            NotificationEndpoint.tenant_id == tenant_id,
            NotificationEndpoint.workspace_id == workspace_id,
            NotificationEndpoint.scope == "workspace",
            NotificationEndpoint.status == "active",
        )
    )
    endpoints = [
        endpoint
        for endpoint in (await db.exec(query)).scalars()
        if category in (endpoint.categories_json or DEFAULT_WORKSPACE_CATEGORIES)
    ]
    if not endpoints:
        return []
    notification = _notification(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_id=f"{WORKSPACE_RECIPIENT_PREFIX}{workspace_id}",
        title=title,
        content=content,
        severity=severity,
        source_module=source_module,
        action=None,
        meta={**(meta or {}), "category": category},
    )
    db.add(notification)
    now = utc_now()
    return [stage_delivery(db, notification, endpoint, now) for endpoint in endpoints]
