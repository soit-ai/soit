"""test_run_failed_notification

Observe already showed a failed run; the notification centre stayed empty. This
covers the handler that closes that gap, and the two cases where staying quiet
is the right answer.
"""

import pytest
from sqlmodel import select

from app.kernel.commons.ids import generate_run_id
from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run
from app.modules.identity.domain.models import WorkspaceMembership
from app.modules.notification.domain.models import Notification, NotificationPreference
from app.modules.notification.handlers.on_run_failed import handle_run_failed

pytestmark = pytest.mark.asyncio


async def _run(db, ctx, *, status: str = "failed", sandbox: bool = False) -> Run:
    run = Run(
        id=generate_run_id(),
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        trace_id="trace_failed",
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id="support-triage",
        subject_version_id="agtv_1",
        status=status,
        sandbox=sandbox,
        error_message="MODEL_CAPABILITY_UNAVAILABLE: chat",
        started_at=utc_now(),
    )
    db.add(run)
    await db.commit()
    return run


async def _event(db, ctx, run: Run, *, status: str = "failed") -> EventOutbox:
    row = EventOutbox(
        event_id=f"evt_{run.id}",
        event_type="run.status.updated",
        idempotency_key=f"run.status.updated:{run.id}:{status}",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id=run.id,
        payload_json={
            "run_id": run.id,
            "status": status,
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
        },
    )
    db.add(row)
    await db.commit()
    return row


async def _member(db, ctx, user_id: str, role: str = "Owner") -> None:
    db.add(
        WorkspaceMembership(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id=user_id,
            role=role,
        )
    )
    await db.commit()


async def _notifications(db, user_id: str) -> list[Notification]:
    rows = (await db.exec(select(Notification).where(Notification.user_id == user_id))).all()
    return [row if hasattr(row, "id") else row[0] for row in rows]


async def test_a_failed_run_reaches_the_people_who_can_act_on_it(async_db, ctx):
    await _member(async_db, ctx, "u_owner", "Owner")
    await _member(async_db, ctx, "u_dev", "Dev")
    await _member(async_db, ctx, "u_viewer", "Viewer")
    run = await _run(async_db, ctx)

    await handle_run_failed(async_db, await _event(async_db, ctx, run))
    await async_db.commit()

    assert len(await _notifications(async_db, "u_owner")) == 1
    assert len(await _notifications(async_db, "u_dev")) == 1
    # A viewer cannot fix it, so telling them is noise.
    assert await _notifications(async_db, "u_viewer") == []

    notification = (await _notifications(async_db, "u_owner"))[0]
    assert run.id in (notification.content or "")
    assert notification.action["target"] == f"/observe/runs/{run.id}"


async def test_a_run_that_did_not_fail_notifies_nobody(async_db, ctx):
    await _member(async_db, ctx, "u_owner")
    run = await _run(async_db, ctx, status="succeeded")

    await handle_run_failed(async_db, await _event(async_db, ctx, run, status="succeeded"))
    await async_db.commit()

    assert await _notifications(async_db, "u_owner") == []


async def test_a_rehearsal_failure_stays_quiet(async_db, ctx):
    """Pre-release regression fails while a set is being written."""
    await _member(async_db, ctx, "u_owner")
    run = await _run(async_db, ctx, sandbox=True)

    await handle_run_failed(async_db, await _event(async_db, ctx, run))
    await async_db.commit()

    assert await _notifications(async_db, "u_owner") == []


async def test_a_member_who_switched_the_category_off_is_not_notified(async_db, ctx):
    await _member(async_db, ctx, "u_quiet")
    async_db.add(
        NotificationPreference(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id="u_quiet",
            categories_json={"task": False},
        )
    )
    await async_db.commit()
    run = await _run(async_db, ctx)

    await handle_run_failed(async_db, await _event(async_db, ctx, run))
    await async_db.commit()

    assert await _notifications(async_db, "u_quiet") == []


async def test_redelivering_the_same_event_does_not_notify_twice(async_db, ctx):
    await _member(async_db, ctx, "u_owner")
    run = await _run(async_db, ctx)
    event = await _event(async_db, ctx, run)

    await handle_run_failed(async_db, event)
    await async_db.commit()
    await handle_run_failed(async_db, event)
    await async_db.commit()

    assert len(await _notifications(async_db, "u_owner")) == 1
