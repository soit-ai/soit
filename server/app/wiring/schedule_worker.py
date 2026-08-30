"""The worker that fires due schedules.

It lives in wiring rather than beside the schedule model because firing means
handing work to the same services the API uses, and the kernel does not know
how those are assembled -- the durable interaction worker sits here for the
same reason.

It owns when, not how: firing hands the work to the same durable path the API
uses, so a scheduled run is an ordinary run with an ordinary ledger entry. What
this adds is the claim -- several replicas may be running, and exactly one of
them must fire each occurrence.

Nothing is executed inline. An agent is enqueued as a durable interaction and
picked up by the interaction worker; a workflow is started the way the API
starts one, and recovered by the workflow reaper if the process dies.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import and_
from sqlmodel import Session

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.common import lease
from app.kernel.runtime.db.models.responses import ResponseInteraction
from app.kernel.runtime.db.models.schedules import Schedule
from app.kernel.runtime.schedules.cron import CronError, next_fire_after

logger = logging.getLogger(__name__)

SCHEDULE_ORIGIN = "schedule"
"""Recorded on what a firing produces, so a run can be traced back to it."""


def _context(schedule: Schedule) -> RequestContext:
    """Act as the schedule, not as whoever last edited it.

    Attributing a 3am run to a person who was asleep would make the audit
    trail read as if they had started it.
    """
    return RequestContext(
        tenant_id=schedule.tenant_id,
        workspace_id=schedule.workspace_id,
        user_id=f"system:schedule:{schedule.id}",
    )


def _enqueue_agent_interaction(db: Session, schedule: Schedule) -> str:
    """Queue an agent run on the durable interaction path.

    The interaction worker claims queued rows, so the schedule's job is done
    once this row exists: no execution happens on the scheduler's own loop, and
    a scheduler crash between here and the run starting loses nothing.
    """
    interaction_id = f"sched_{generate_ulid()}"
    inputs = dict(schedule.input_json or {})
    payload = {
        "agent_id": schedule.target_id,
        "input": inputs.get("input") or inputs.get("message") or "",
        "metadata": {
            "origin": SCHEDULE_ORIGIN,
            "schedule_id": schedule.id,
            "schedule_name": schedule.name,
        },
    }
    if inputs.get("thread_id"):
        payload["thread_id"] = inputs["thread_id"]

    db.add(
        ResponseInteraction(
            tenant_id=schedule.tenant_id,
            workspace_id=schedule.workspace_id,
            interaction_id=interaction_id,
            thread_id=str(inputs.get("thread_id") or ""),
            request_hash=f"{SCHEDULE_ORIGIN}:{schedule.id}:{interaction_id}",
            kind="run",
            status="queued",
            execution_json={"mode": "direct", "payload": payload},
            request_context_json={
                "tenant_id": schedule.tenant_id,
                "workspace_id": schedule.workspace_id,
                "user_id": _context(schedule).user_id,
            },
            created_by=_context(schedule).user_id,
        )
    )
    db.commit()
    return interaction_id


async def _start_workflow(db: Session, schedule: Schedule) -> str:
    """Start a workflow run the way the API starts one."""
    from app.wiring.services import build_workflow_service

    service = build_workflow_service(db=db, ctx=_context(schedule))
    result = await service.execute_workflow(
        schedule.target_id,
        dict(schedule.input_json or {}),
    )
    return str(result.get("run_id") or "")


def _advance(schedule: Schedule, fired_at: datetime) -> datetime | None:
    """Work out the firing after this one.

    Computed from now rather than from the occurrence just fired: with catch-up
    off, a scheduler that was down for a day resumes at the next real
    occurrence instead of replaying the day it missed.
    """
    if not schedule.enabled:
        return None
    try:
        base = schedule.next_fire_at if schedule.catch_up else fired_at
        if base is None:
            base = fired_at
        return next_fire_after(schedule.cron, base, timezone=schedule.timezone)
    except CronError:
        logger.exception("Schedule %s has an expression that no longer parses", schedule.id)
        return None


class ScheduleWorker:
    """Claim due schedules and fire them, one occurrence each."""

    def __init__(
        self,
        db_factory: Callable[[], Session],
        *,
        worker_id: str | None = None,
        lease_seconds: int = 60,
    ) -> None:
        self.db_factory = db_factory
        self.worker_id = worker_id or f"scheduler-{generate_ulid()}"
        self.lease_seconds = lease.normalize_lease_seconds(lease_seconds)

    def _claim_due(self, db: Session, now: datetime) -> Schedule | None:
        return lease.claim_next(
            db,
            Schedule,
            worker_id=self.worker_id,
            lease_seconds=self.lease_seconds,
            extra_where=(
                and_(
                    Schedule.enabled.is_(True),
                    Schedule.next_fire_at.is_not(None),
                    Schedule.next_fire_at <= now,
                ),
            ),
            order_by=Schedule.next_fire_at.asc(),
            now=now,
        )

    async def fire_once(self) -> str | None:
        """Fire the next due schedule, returning its id, or None when none is due.

        An id rather than the row: the session this ran on closes here, and
        handing back a detached object invites a caller to read from it.
        """
        db = self.db_factory()
        try:
            now = utc_now()
            schedule = self._claim_due(db, now)
            if schedule is None:
                return None

            await self.fire_schedule(schedule, db=db, now=now)
            return schedule.id
        finally:
            db.close()

    async def fire_schedule(
        self,
        schedule: Schedule,
        *,
        db: Session | None = None,
        now: datetime | None = None,
        advance: bool = True,
    ) -> Schedule:
        """Fire one schedule and record how it went.

        Also the path a manual "run now" takes, so a test firing behaves
        exactly like a real one instead of proving a second implementation
        works. A manual firing leaves the next occurrence alone: asking for a
        run now is not the same as moving the schedule.
        """
        session = db or self.db_factory()
        owns_session = db is None
        moment = now or utc_now()
        try:
            try:
                if schedule.target_kind == "workflow":
                    run_id = await _start_workflow(session, schedule)
                else:
                    run_id = _enqueue_agent_interaction(session, schedule)
                schedule.last_status = "started"
                schedule.last_run_id = run_id or None
                schedule.last_error = None
            except Exception as exc:
                # A target that has been deleted, or a workflow that will not
                # compile, must not stop the schedule from being tried again at
                # its next occurrence -- and must be visible on the row.
                logger.exception("Schedule %s failed to fire", schedule.id)
                schedule.last_status = "failed"
                schedule.last_error = f"{type(exc).__name__}: {exc}"[:512]

            schedule.last_fired_at = moment
            if advance:
                schedule.next_fire_at = _advance(schedule, moment)
            schedule.status = "queued"
            schedule.lease_owner = None
            schedule.lease_expires_at = None
            schedule.updated_at = utc_now()
            session.add(schedule)
            session.commit()
            return schedule
        finally:
            if owns_session:
                session.close()

    async def run_loop(self, *, poll_interval: float = 15.0) -> None:
        """Fire due schedules until cancelled.

        Each tick drains everything due, so a burst of schedules sharing one
        minute all fire in that minute rather than one per tick.
        """
        while True:
            try:
                while await self.fire_once() is not None:
                    pass
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Schedule sweep failed")
            await asyncio.sleep(max(1.0, float(poll_interval)))
