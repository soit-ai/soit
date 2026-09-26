"""Notifications for budget thresholds.

Consumes billing.budget.threshold_reached outbox events and tells workspace
Owners and Admins, through their inboxes and endpoints, and the workspace
endpoints subscribed to alerts, how much of which budget is spent. The
consumer checkpoint keeps the fan-out idempotent per event.
"""

from __future__ import annotations

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.events.checkpoint import try_claim_consumer_slot
from app.kernel.runtime.db.models.events import EventOutbox
from app.modules.notification.application.fanout import (
    notify_members,
    notify_workspace_endpoints,
)

CONSUMER_NAME = "notification.budget.threshold"
_ALERT_ROLES = ("Owner", "Admin")


def _severity(threshold: int, hard_stop: bool) -> str:
    if threshold >= 100:
        return "error" if hard_stop else "warning"
    return "warning" if threshold >= 80 else "info"


async def handle_budget_threshold(db: AsyncSession, row: EventOutbox) -> None:
    """Fan a budget threshold out to administrators and workspace endpoints."""
    if not await try_claim_consumer_slot(
        db,
        consumer_name=CONSUMER_NAME,
        event_id=row.event_id,
        result="budget_threshold_notification",
    ):
        return
    payload = row.payload_json or {}
    tenant_id = str(row.tenant_id or "")
    workspace_id = str(row.workspace_id or "")
    if not tenant_id or not workspace_id or not payload.get("budget_id"):
        return

    threshold = int(payload.get("threshold") or 0)
    hard_stop = bool(payload.get("hard_stop"))
    name = payload.get("budget_name") or payload.get("budget_id")
    currency = payload.get("currency") or ""
    title = f"Budget '{name}' reached {threshold}%"
    content = (
        f"{payload.get('spent')} of {payload.get('amount')} {currency} spent this "
        f"{payload.get('period')}."
    )
    if threshold >= 100 and hard_stop:
        content = f"{content} Calls it covers are refused until the period resets."
    meta = {
        "budget_id": payload.get("budget_id"),
        "threshold": threshold,
        "percent": payload.get("percent"),
        "period_start": payload.get("period_start"),
    }
    severity = _severity(threshold, hard_stop)

    await notify_members(
        db,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        roles=_ALERT_ROLES,
        category="alert",
        title=title,
        content=content,
        severity=severity,
        source_module="billing",
        action={"type": "open", "target": "/govern/budgets"},
        meta=meta,
    )
    await notify_workspace_endpoints(
        db,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        category="alert",
        title=title,
        content=content,
        severity=severity,
        source_module="billing",
        meta=meta,
    )
    await db.flush()
