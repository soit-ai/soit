"""In-app notifications for runs that failed.

Observe already showed a failed run; the notification centre stayed empty, so
nobody learned about a failure unless they happened to be looking at Observe.

One notification per failed run, to the members who can act on it. The consumer
checkpoint keeps that true when the same event is redelivered.
"""

from __future__ import annotations

import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.events.checkpoint import try_claim_consumer_slot
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run
from app.modules.notification.application.fanout import (
    notify_members,
    notify_workspace_endpoints,
)

logger = logging.getLogger(__name__)

CONSUMER_NAME = "notification.run.failed"

_ALERT_ROLES = ("Owner", "Admin", "Dev")
"""Who hears about it: the people who can look at the run and fix it."""

_CATEGORY = "task"
"""The preference category a member can switch off."""


async def handle_run_failed(db: AsyncSession, row: EventOutbox) -> None:
    """Notify a workspace that one of its runs failed."""
    payload = row.payload_json or {}
    status = str(payload.get("status") or "")
    if status != "failed":
        return

    run_id = str(payload.get("run_id") or row.run_id or "")
    if not run_id:
        return

    if not await try_claim_consumer_slot(
        db,
        consumer_name=CONSUMER_NAME,
        event_id=row.event_id,
        result="run_failed_notification",
    ):
        return

    run = await db.get(Run, run_id)
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

    await notify_members(
        db,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        roles=_ALERT_ROLES,
        category=_CATEGORY,
        title="A run failed",
        content=content,
        severity="error",
        source_module="observe",
        action={"type": "open", "target": f"/observe/runs/{run_id}"},
        meta={"run_id": run_id, "subject_id": subject},
    )
    await notify_workspace_endpoints(
        db,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        category=_CATEGORY,
        title="A run failed",
        content=content,
        severity="error",
        source_module="observe",
        meta={"run_id": run_id, "subject_id": subject},
    )
    await db.flush()
