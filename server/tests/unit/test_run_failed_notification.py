"""test_run_failed_notification

Observe already showed a failed run; the notification centre stayed empty. This
covers the handler that closes that gap, and the two cases where staying quiet
is the right answer.
"""

from sqlmodel import select

from app.kernel.commons.ids import generate_run_id
from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run
from app.modules.identity.domain.models import WorkspaceMembership
from app.modules.notification.domain.models import Notification, NotificationPreference
from app.modules.notification.handlers.on_run_failed import handle_run_failed


def _run(db, ctx, *, status: str = "failed", sandbox: bool = False) -> Run:
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
    db.commit()
    return run


def _event(db, ctx, run: Run, *, status: str = "failed") -> EventOutbox:
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
    db.commit()
    return row


def _member(db, ctx, user_id: str, role: str = "Owner") -> None:
    db.add(
        WorkspaceMembership(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id=user_id,
            role=role,
        )
    )
    db.commit()


def _notifications(db, user_id: str) -> list[Notification]:
    rows = db.exec(select(Notification).where(Notification.user_id == user_id)).all()
    return [row if hasattr(row, "id") else row[0] for row in rows]


def test_a_failed_run_reaches_the_people_who_can_act_on_it(db, ctx):
    _member(db, ctx, "u_owner", "Owner")
    _member(db, ctx, "u_dev", "Dev")
    _member(db, ctx, "u_viewer", "Viewer")
    run = _run(db, ctx)

    handle_run_failed(db, _event(db, ctx, run))
    db.commit()

    assert len(_notifications(db, "u_owner")) == 1
    assert len(_notifications(db, "u_dev")) == 1
    # A viewer cannot fix it, so telling them is noise.
    assert _notifications(db, "u_viewer") == []

    notification = _notifications(db, "u_owner")[0]
    assert run.id in (notification.content or "")
    assert notification.action["target"] == f"/observe/runs/{run.id}"


def test_a_run_that_did_not_fail_notifies_nobody(db, ctx):
    _member(db, ctx, "u_owner")
    run = _run(db, ctx, status="succeeded")

    handle_run_failed(db, _event(db, ctx, run, status="succeeded"))
    db.commit()

    assert _notifications(db, "u_owner") == []


def test_a_rehearsal_failure_stays_quiet(db, ctx):
    """Pre-release regression fails while a set is being written."""
    _member(db, ctx, "u_owner")
    run = _run(db, ctx, sandbox=True)

    handle_run_failed(db, _event(db, ctx, run))
    db.commit()

    assert _notifications(db, "u_owner") == []


def test_a_member_who_switched_the_category_off_is_not_notified(db, ctx):
    _member(db, ctx, "u_quiet")
    db.add(
        NotificationPreference(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id="u_quiet",
            categories_json={"task": False},
        )
    )
    db.commit()
    run = _run(db, ctx)

    handle_run_failed(db, _event(db, ctx, run))
    db.commit()

    assert _notifications(db, "u_quiet") == []


def test_redelivering_the_same_event_does_not_notify_twice(db, ctx):
    _member(db, ctx, "u_owner")
    run = _run(db, ctx)
    event = _event(db, ctx, run)

    handle_run_failed(db, event)
    db.commit()
    handle_run_failed(db, event)
    db.commit()

    assert len(_notifications(db, "u_owner")) == 1
