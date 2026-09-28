"""Release a budget hold once the call it was taken for has its cost committed.

A call is checked against its budgets on the session that later records its
cost, so the holds wait on that session. When a model or tool cost row for the
same run is flushed, the oldest waiting hold of that run is settled (storage
and vector rows are written by calls that take no hold); settled holds are
released after the transaction that wrote the cost commits, when other callers
can read the cost instead, or rolls back, when there is nothing left to wait
for. When a run ends, the holds its calls still keep are settled too: a call
that failed records no cost, and without this its hold would stay until it
expired, so a burst of failing calls would hold a budget shut for minutes.
A hold whose run never ends on this session expires on its own.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.runtime.db.models.runs import Run, RunCostEntry

if TYPE_CHECKING:
    from app.modules.billing.application.budgets import BudgetReservations, HoldGrant

logger = logging.getLogger(__name__)

_INFO_KEY = "soit.budget_holds"
_HOLDING_PORTS = frozenset({"llm", "tools"})
_ENDED_RUN_STATUSES = frozenset({"succeeded", "failed", "canceled", "expired"})
"""The ports whose calls are checked against budgets, by their cost rows' ``source_port``."""
_RELEASES: set[asyncio.Task[None]] = set()


@dataclass
class _Hold:
    run_id: str | None
    grant: HoldGrant
    reservations: BudgetReservations


@dataclass
class SessionHolds:
    """The holds taken on one session, waiting for their calls' costs."""

    pending: list[_Hold] = field(default_factory=list[_Hold])
    settled: list[_Hold] = field(default_factory=list[_Hold])

    def settle(self, run_id: str | None) -> None:
        if run_id is None:
            return
        for index, hold in enumerate(self.pending):
            if hold.run_id == run_id:
                self.settled.append(self.pending.pop(index))
                return

    def settle_run(self, run_id: str) -> None:
        ended = [hold for hold in self.pending if hold.run_id == run_id]
        if ended:
            self.pending = [hold for hold in self.pending if hold.run_id != run_id]
            self.settled.extend(ended)

    def after_flush(self, session: Session, _flush_context: Any) -> None:
        for instance in session.new:
            if isinstance(instance, RunCostEntry) and instance.source_port in _HOLDING_PORTS:
                self.settle(instance.run_id)
        if not self.pending:
            return
        for instance in (*session.new, *session.dirty):
            if isinstance(instance, Run) and instance.status in _ENDED_RUN_STATUSES:
                self.settle_run(instance.id)

    def release_settled(self, _session: Session) -> None:
        holds, self.settled = self.settled, []
        if holds:
            _schedule_release(holds)


async def _release(holds: list[_Hold]) -> None:
    for hold in holds:
        try:
            await hold.reservations.release(hold.grant)
        except Exception:
            logger.warning("Budget hold not released; it expires on its own", exc_info=True)


def _schedule_release(holds: list[_Hold]) -> None:
    # Commit hooks are synchronous; the release runs on the session's loop.
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(_release(holds))
    _RELEASES.add(task)
    task.add_done_callback(_RELEASES.discard)


def session_holds(db: AsyncSession) -> SessionHolds | None:
    return db.sync_session.info.get(_INFO_KEY)


def track_hold(
    db: AsyncSession,
    grant: HoldGrant,
    reservations: BudgetReservations,
    *,
    run_id: str | None,
) -> None:
    """Keep ``grant`` on ``db`` until the call's cost is committed there."""
    if not grant.budget_ids:
        return
    sync_session = db.sync_session
    holds = sync_session.info.get(_INFO_KEY)
    if holds is None:
        holds = SessionHolds()
        sync_session.info[_INFO_KEY] = holds
        event.listen(sync_session, "after_flush", holds.after_flush)
        event.listen(sync_session, "after_commit", holds.release_settled)
        event.listen(sync_session, "after_rollback", holds.release_settled)
    holds.pending.append(_Hold(run_id, grant, reservations))
