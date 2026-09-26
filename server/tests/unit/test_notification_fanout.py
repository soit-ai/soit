"""Alerts reach inboxes, members' own endpoints and workspace endpoints."""

from __future__ import annotations

from typing import Any

import pytest
from sqlmodel import select

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.events import EventOutbox
from app.modules.billing.events import BUDGET_THRESHOLD_REACHED
from app.modules.identity.domain.models import WorkspaceMembership
from app.modules.notification.domain.models import (
    Notification,
    NotificationDelivery,
    NotificationEndpoint,
    NotificationPreference,
)
from app.modules.notification.handlers.apprise_delivery import (
    handle_notification_delivery_outbox,
)
from app.modules.notification.handlers.on_budget_threshold import (
    handle_budget_threshold,
)
from app.modules.notification.infra.repository import NotificationRepository

pytestmark = pytest.mark.asyncio


async def _member(async_db, ctx: RequestContext, user_id: str, role: str) -> None:
    async_db.add(
        WorkspaceMembership(
            tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, user_id=user_id, role=role
        )
    )


def _endpoint(ctx: RequestContext, name: str, **fields: Any) -> NotificationEndpoint:
    values: dict[str, Any] = {
        "tenant_id": ctx.tenant_id,
        "workspace_id": ctx.workspace_id,
        "user_id": "u_admin",
        "name": name,
        "kind": "webhook",
        "secret_id": f"sec_{name}",
        "display_target": "json://***",
        **fields,
    }
    return NotificationEndpoint(**values)


def _threshold_event(ctx: RequestContext, threshold: int = 80) -> EventOutbox:
    return EventOutbox(
        event_id=f"evt_budget_b1_2026-09-01_{threshold}",
        event_type=BUDGET_THRESHOLD_REACHED,
        idempotency_key=f"evt_budget_b1_2026-09-01_{threshold}",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        payload_json={
            "budget_id": "bud_1",
            "budget_name": "Team monthly",
            "threshold": threshold,
            "percent": "81.00",
            "spent": "81",
            "amount": "100",
            "currency": "USD",
            "period": "month",
            "period_start": "2026-09-01",
            "hard_stop": True,
        },
    )


async def _rows(async_db, model: type) -> list[Any]:
    return list((await async_db.exec(select(model))).all())


class _Secrets:
    async def get_secret(self, *, secret_id: str) -> str:
        return f"json://hooks.example.com/{secret_id}"


class _Egress:
    async def authorize(self, *args: Any, **kwargs: Any) -> None:
        return None


async def test_a_budget_threshold_reaches_admins_and_the_team_channel(async_db, ctx) -> None:
    await _member(async_db, ctx, "u_owner", "Owner")
    await _member(async_db, ctx, "u_admin", "Admin")
    await _member(async_db, ctx, "u_dev", "Dev")
    async_db.add(_endpoint(ctx, "team", scope="workspace"))
    async_db.add(_endpoint(ctx, "on-call", scope="workspace", categories_json=["task"]))
    await async_db.commit()
    event = _threshold_event(ctx)

    await handle_budget_threshold(async_db, event)
    await handle_budget_threshold(async_db, event)
    await async_db.commit()

    notifications = await _rows(async_db, Notification)
    inboxes = sorted(n.user_id for n in notifications if not n.user_id.startswith("workspace:"))
    assert inboxes == ["u_admin", "u_owner"]
    assert all("Team monthly" in n.title and "80%" in n.title for n in notifications)
    deliveries = await _rows(async_db, NotificationDelivery)
    assert len(deliveries) == 1
    team = (await async_db.exec(select(NotificationEndpoint).where(NotificationEndpoint.name == "team"))).one()
    assert deliveries[0].endpoint_id == team.id
    queued = [
        row
        for row in await _rows(async_db, EventOutbox)
        if row.event_type == "notification.delivery.requested"
    ]
    assert [row.payload_json["delivery_id"] for row in queued] == [deliveries[0].id]

    sent: list[tuple[str, str, str]] = []

    async def sender(url: str, *, title: str, body: str) -> bool:
        sent.append((url, title, body))
        return True

    await handle_notification_delivery_outbox(
        async_db, queued[0], secrets_port=_Secrets(), sender=sender, egress_guard=_Egress()
    )
    await async_db.commit()

    await async_db.refresh(deliveries[0])
    assert deliveries[0].status == "sent"
    assert sent == [("json://hooks.example.com/sec_team", "Budget 'Team monthly' reached 80%", "81 of 100 USD spent this month.")]


async def test_a_members_own_endpoints_follow_their_delivery_mode(async_db, ctx) -> None:
    await _member(async_db, ctx, "u_admin", "Admin")
    async_db.add(
        NotificationPreference(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id="u_admin",
            delivery_mode="in_app_email",
        )
    )
    async_db.add(_endpoint(ctx, "mail", kind="email"))
    async_db.add(_endpoint(ctx, "hook", kind="webhook"))
    await async_db.commit()

    await handle_budget_threshold(async_db, _threshold_event(ctx))
    await async_db.commit()

    deliveries = await _rows(async_db, NotificationDelivery)
    mail = (await async_db.exec(select(NotificationEndpoint).where(NotificationEndpoint.name == "mail"))).one()
    assert [delivery.endpoint_id for delivery in deliveries] == [mail.id]


async def test_members_who_switched_alerts_off_hear_nothing(async_db, ctx) -> None:
    await _member(async_db, ctx, "u_admin", "Admin")
    async_db.add(
        NotificationPreference(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id="u_admin",
            categories_json={"alert": False},
        )
    )
    await async_db.commit()

    await handle_budget_threshold(async_db, _threshold_event(ctx))
    await async_db.commit()

    assert await _rows(async_db, Notification) == []


async def test_workspace_endpoints_stay_out_of_personal_views(async_db, ctx) -> None:
    admin = RequestContext(
        tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, user_id="u_admin"
    )
    async_db.add(_endpoint(ctx, "personal"))
    async_db.add(_endpoint(ctx, "team", scope="workspace"))
    await async_db.commit()

    listed = await NotificationRepository(async_db, admin).list_endpoints("u_admin")

    assert [endpoint.name for endpoint in listed] == ["personal"]
