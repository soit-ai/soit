"""Notifications for billing credit balance alerts.

Consumes billing.credit.balance_low outbox events. Each workspace Owner and
Admin who keeps alerts on gets an inbox notification, delivered to their own
endpoints as their preferences say, and the workspace endpoints subscribed to
alerts get it too. The consumer checkpoint keeps the fan-out idempotent per
event.
"""

from __future__ import annotations

import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.events.checkpoint import try_claim_consumer_slot
from app.kernel.runtime.db.models.events import EventOutbox
from app.modules.notification.application.fanout import (
    notify_members,
    notify_workspace_endpoints,
)

logger = logging.getLogger(__name__)

CONSUMER_NAME = "notification.credit.balance_low"
_ALERT_ROLES = ("Owner", "Admin")

_TITLES = {
    "low": "Workspace credit balance is low",
    "exhausted": "Workspace credit balance is exhausted",
}
_SEVERITIES = {"low": "warning", "exhausted": "error"}


async def handle_credit_balance_low(db: AsyncSession, row: EventOutbox) -> None:
    """Fan a balance alert out to administrators and workspace endpoints."""
    if not await try_claim_consumer_slot(
        db,
        consumer_name=CONSUMER_NAME,
        event_id=row.event_id,
        result="credit_balance_notification",
    ):
        return

    payload = row.payload_json or {}
    state = str(payload.get("state") or "")
    tenant_id = payload.get("tenant_id") or row.tenant_id
    workspace_id = payload.get("workspace_id") or row.workspace_id
    if state not in _TITLES or not tenant_id or not workspace_id:
        return

    balance = payload.get("balance")
    threshold = payload.get("threshold")
    if state == "exhausted":
        content = (
            f"The credit balance is {balance}. Metered invocations are blocked "
            "when enforcement is enabled; top up credits to continue."
        )
    else:
        content = (
            f"The credit balance dropped to {balance}, below the warning "
            f"threshold of {threshold}. Consider topping up credits."
        )
    meta = {
        "state": state,
        "balance": balance,
        "threshold": threshold,
        "ledger_entry_id": payload.get("ledger_entry_id"),
        "run_id": payload.get("run_id"),
    }

    notified = await notify_members(
        db,
        tenant_id=str(tenant_id),
        workspace_id=str(workspace_id),
        roles=_ALERT_ROLES,
        category="alert",
        title=_TITLES[state],
        content=content,
        severity=_SEVERITIES[state],
        source_module="billing",
        meta=meta,
    )
    delivered = await notify_workspace_endpoints(
        db,
        tenant_id=str(tenant_id),
        workspace_id=str(workspace_id),
        category="alert",
        title=_TITLES[state],
        content=content,
        severity=_SEVERITIES[state],
        source_module="billing",
        meta=meta,
    )
    if not notified and not delivered:
        logger.warning(
            "No one to notify for credit alert: tenant=%s workspace=%s",
            tenant_id,
            workspace_id,
        )
    await db.flush()
