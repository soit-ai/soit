"""In-app notifications for runs that failed.

Observe already showed a failed run; the notification centre stayed empty, so
nobody learned about a failure unless they happened to be looking at Observe.

One notification per failed run, to the members who can act on it. The consumer
checkpoint keeps that true when the same event is redelivered.
"""

from __future__ import annotations

import logging

from sqlalchemy import and_, select
from sqlmodel import Session

from app.kernel.commons.ids import generate_notification_id
from app.kernel.commons.time import utc_now
from app.kernel.events.checkpoint import try_claim_consumer_slot
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run
from app.modules.identity.domain.models import WorkspaceMembership
from app.modules.notification.domain.models import Notification, NotificationPreference

logger = logging.getLogger(__name__)

CONSUMER_NAME = "notification.run.failed"

_ALERT_ROLES = ("Owner", "Admin", "Dev")
"""Who hears about it: the people who can look at the run and fix it."""

_CATEGORY = "task"
"""The preference category a member can switch off."""


def _members_to_notify(db: Session, tenant_id: str, workspace_id: str) -> list[str]:
    query = select(WorkspaceMembership).where(
        and_(
            WorkspaceMembership.tenant_id == tenant_id,
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.role.in_(_ALERT_ROLES),
        )
    )
    rows = list(db.exec(query).all())
    members = [item if hasattr(item, "user_id") else item[0] for item in rows]
    return [member.user_id for member in members]


def _wants_it(db: Session, user_id: str) -> bool:
    """Whether this member left run alerts switched on.

    Absent preferences mean the default, which is on: a member who never opened
    the settings still hears that their agents are failing.
    """
    query = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    row = db.exec(query).first()
    preference = row if row is None or hasattr(row, "categories_json") else row[0]
    if preference is None:
        return True
    categories = preference.categories_json or {}
    return bool(categories.get(_CATEGORY, True))


def handle_run_failed(db: Session, row: EventOutbox) -> None:
    """Notify a workspace that one of its runs failed."""
    payload = row.payload_json or {}
    status = str(payload.get("status") or "")
    if status != "failed":
        return

    run_id = str(payload.get("run_id") or row.run_id or "")
    if not run_id:
        return

    if not try_claim_consumer_slot(
        db,
        consumer_name=CONSUMER_NAME,
        event_id=row.event_id,
        result="run_failed_notification",
    ):
        return

    run = db.get(Run, run_id)
    tenant_id = str(payload.get("tenant_id") or row.tenant_id or (run.tenant_id if run else ""))
    workspace_id = str(
        payload.get("workspace_id") or row.workspace_id or (run.workspace_id if run else "")
    )
    if not tenant_id or not workspace_id:
        return

    # A rehearsal failing is expected while a regression set is being written,
    # and would drown the real failures.
    if run is not None and getattr(run, "sandbox", False):
        return

    subject = (run.subject_id if run else None) or "an agent"
    reason = (run.error_message if run else None) or (run.error_code if run else None)
    content = f"Run {run_id} on {subject} failed."
    if reason:
        content = f"{content} {reason}"

    now = utc_now()
    for user_id in _members_to_notify(db, tenant_id, workspace_id):
        if not _wants_it(db, user_id):
            continue
        db.add(
            Notification(
                id=generate_notification_id(),
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                user_id=user_id,
                type="alert",
                severity="error",
                status="unread",
                title="A run failed",
                content=content,
                source_module="observe",
                action={"type": "open", "target": f"/observe/runs/{run_id}"},
                meta={"run_id": run_id, "subject_id": subject},
                created_at=now,
                updated_at=now,
            )
        )
    db.flush()
