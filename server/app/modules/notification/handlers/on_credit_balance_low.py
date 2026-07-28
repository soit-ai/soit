"""In-app notifications for billing credit balance alerts.

Consumes billing.credit.balance_low outbox events and writes one inbox
notification per workspace Owner/Admin. The consumer checkpoint keeps the
fan-out idempotent per event.
"""

from __future__ import annotations

import logging

from sqlalchemy import and_, select
from sqlmodel import Session

from app.kernel.commons.ids import generate_notification_id
from app.kernel.commons.time import utc_now
from app.kernel.events.checkpoint import try_claim_consumer_slot
from app.kernel.runtime.db.models.events import EventOutbox
from app.modules.identity.domain.models import WorkspaceMembership
from app.modules.notification.domain.models import Notification

logger = logging.getLogger(__name__)

CONSUMER_NAME = "notification.credit.balance_low"
_ALERT_ROLES = ("Owner", "Admin")

_TITLES = {
    "low": "Workspace credit balance is low",
    "exhausted": "Workspace credit balance is exhausted",
}
_SEVERITIES = {"low": "warning", "exhausted": "error"}


def handle_credit_balance_low(db: Session, row: EventOutbox) -> None:
    """Fan a balance alert out to workspace administrators' inboxes."""
    if not try_claim_consumer_slot(
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

    members_query = select(WorkspaceMembership).where(
        and_(
            WorkspaceMembership.tenant_id == tenant_id,
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.role.in_(_ALERT_ROLES),
        )
    )
    rows = list(db.exec(members_query).all())
    members = [item if hasattr(item, "user_id") else item[0] for item in rows]
    if not members:
        logger.warning(
            "No Owner/Admin members to notify for credit alert: tenant=%s workspace=%s",
            tenant_id,
            workspace_id,
        )
        return

    now = utc_now()
    for member in members:
        db.add(
            Notification(
                id=generate_notification_id(),
                tenant_id=str(tenant_id),
                workspace_id=str(workspace_id),
                user_id=member.user_id,
                type="alert",
                severity=_SEVERITIES[state],
                status="unread",
                title=_TITLES[state],
                content=content,
                source_module="billing",
                meta={
                    "state": state,
                    "balance": balance,
                    "threshold": threshold,
                    "ledger_entry_id": payload.get("ledger_entry_id"),
                    "run_id": payload.get("run_id"),
                },
                created_at=now,
                updated_at=now,
            )
        )
    db.flush()
