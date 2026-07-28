"""Shared lease primitives for durable runtime workers.

Durable workers claim persisted work rows, hold a time-bounded lease while they
execute, and renew that lease with a heartbeat. A worker that dies stops
renewing, so its rows become claimable again once the lease expires. Every
runtime domain that executes work outside a request must use these helpers so
claim, renewal and orphan recovery share one semantic.

A model participating in leasing must expose ``status``, ``lease_owner``,
``lease_expires_at`` and ``attempt_count`` columns.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, TypeVar

from sqlalchemy import and_, or_, update
from sqlalchemy.orm import Session
from sqlmodel import select

from app.kernel.commons.time import utc_now

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT")

MIN_LEASE_SECONDS = 30
MIN_HEARTBEAT_INTERVAL_SECONDS = 5.0
LEASE_RENEWALS_PER_LEASE = 3


class LeaseRenewal(str, Enum):
    """Outcome of a single lease renewal attempt."""

    RENEWED = "renewed"
    """The lease is still owned by this worker and was extended."""

    TERMINAL = "terminal"
    """This worker still owns the row but it already reached a terminal status."""

    LOST = "lost"
    """Another worker took the row over, or the attempt was superseded."""


def normalize_lease_seconds(value: int | float | None) -> int:
    """Clamp a configured lease duration to a safe minimum."""
    return max(MIN_LEASE_SECONDS, int(value or MIN_LEASE_SECONDS))


def heartbeat_interval_for(
    lease_seconds: int,
    *,
    override: float | None = None,
) -> float:
    """Return the renewal interval that keeps a lease alive comfortably.

    An explicit override is honoured as given, which lets tests drive fast
    heartbeats; the floor only guards the interval derived from the lease.
    """
    if override:
        return float(override)
    return max(
        MIN_HEARTBEAT_INTERVAL_SECONDS,
        lease_seconds / LEASE_RENEWALS_PER_LEASE,
    )


def claim_next(
    db: Session,
    model: type[ModelT],
    *,
    worker_id: str,
    lease_seconds: int,
    ready_statuses: Sequence[str] = ("queued",),
    running_status: str = "running",
    extra_where: Sequence[Any] = (),
    order_by: Any = None,
    now: datetime | None = None,
) -> ModelT | None:
    """Claim the oldest ready row, or reclaim one whose lease expired.

    Reclaiming expired rows is what recovers work orphaned by a crashed worker.
    ``SKIP LOCKED`` keeps concurrent workers from contending on the same row;
    SQLite ignores the clause, which is acceptable for single-worker tests.
    """
    moment = now or utc_now()
    claimable = or_(
        model.status.in_(tuple(ready_statuses)),
        and_(
            model.status == running_status,
            model.lease_expires_at.is_not(None),
            model.lease_expires_at < moment,
        ),
    )
    query = select(model).where(claimable)
    for condition in extra_where:
        query = query.where(condition)
    query = query.order_by(
        order_by if order_by is not None else model.created_at.asc()
    )
    query = query.limit(1).with_for_update(skip_locked=True)

    row = db.execute(query).scalars().first()
    if row is None:
        return None

    row.status = running_status
    row.lease_owner = worker_id
    row.lease_expires_at = moment + timedelta(seconds=lease_seconds)
    row.attempt_count = int(getattr(row, "attempt_count", 0) or 0) + 1
    row.updated_at = moment
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def renew_lease(
    db: Session,
    model: type[ModelT],
    primary_key: Any,
    *,
    worker_id: str,
    attempt_count: int,
    lease_seconds: int,
    running_status: str = "running",
) -> LeaseRenewal:
    """Extend a held lease, reporting whether this worker still owns the row."""
    moment = utc_now()
    result = db.execute(
        update(model)
        .where(
            model.id == primary_key,
            model.lease_owner == worker_id,
            model.attempt_count == attempt_count,
            model.status == running_status,
        )
        .values(
            lease_expires_at=moment + timedelta(seconds=lease_seconds),
            updated_at=moment,
        )
    )
    db.commit()
    if result.rowcount == 1:
        return LeaseRenewal.RENEWED

    current = db.get(model, primary_key)
    still_ours = (
        current is not None
        and current.lease_owner == worker_id
        and current.attempt_count == attempt_count
    )
    return LeaseRenewal.TERMINAL if still_ours else LeaseRenewal.LOST


def holds_lease(
    db: Session,
    model: type[ModelT],
    primary_key: Any,
    *,
    worker_id: str,
    attempt_count: int,
) -> bool:
    """Return whether this worker still owns the claim it started with."""
    current = db.get(model, primary_key)
    return (
        current is not None
        and current.lease_owner == worker_id
        and current.attempt_count == attempt_count
    )


def release_lease(
    db: Session,
    model: type[ModelT],
    primary_key: Any,
    *,
    worker_id: str,
    status: str,
) -> bool:
    """Clear the lease when work reaches a terminal status.

    Clearing the lease matters because ``claim_next`` reclaims rows by expiry;
    a terminal row that kept a future expiry would simply never be revisited,
    while one that kept an expired lease could be picked up again.
    """
    moment = utc_now()
    result = db.execute(
        update(model)
        .where(
            model.id == primary_key,
            model.lease_owner == worker_id,
        )
        .values(
            status=status,
            lease_owner=None,
            lease_expires_at=None,
            updated_at=moment,
        )
    )
    db.commit()
    return result.rowcount == 1


class LeaseHeartbeat:
    """Renews a lease on an interval until stopped or lost."""

    def __init__(
        self,
        db_factory: Callable[[], Session],
        model: type[ModelT],
        primary_key: Any,
        *,
        worker_id: str,
        attempt_count: int,
        lease_seconds: int,
        running_status: str = "running",
        interval_seconds: float | None = None,
        log_label: str = "runtime lease",
    ) -> None:
        self.db_factory = db_factory
        self.model = model
        self.primary_key = primary_key
        self.worker_id = worker_id
        self.attempt_count = attempt_count
        self.lease_seconds = lease_seconds
        self.running_status = running_status
        self.interval_seconds = heartbeat_interval_for(
            lease_seconds,
            override=interval_seconds,
        )
        self.log_label = log_label

    async def run(self, stop: asyncio.Event, lease_lost: asyncio.Event) -> None:
        """Renew until ``stop`` is set, the row is terminal, or the lease is lost."""
        while True:
            try:
                await asyncio.wait_for(stop.wait(), timeout=self.interval_seconds)
                return
            except TimeoutError:
                pass

            db: Session | None = None
            try:
                db = self.db_factory()
                outcome = renew_lease(
                    db,
                    self.model,
                    self.primary_key,
                    worker_id=self.worker_id,
                    attempt_count=self.attempt_count,
                    lease_seconds=self.lease_seconds,
                    running_status=self.running_status,
                )
                if outcome is LeaseRenewal.LOST:
                    logger.warning(
                        "%s was lost",
                        self.log_label,
                        extra={"record_id": str(self.primary_key)},
                    )
                    lease_lost.set()
                    return
                if outcome is LeaseRenewal.TERMINAL:
                    return
            except Exception:
                # A transient database error must not kill the worker; the lease
                # simply expires if renewals keep failing, and another worker
                # recovers the row.
                logger.exception(
                    "%s heartbeat failed",
                    self.log_label,
                    extra={"record_id": str(self.primary_key)},
                )
            finally:
                if db is not None:
                    db.close()
