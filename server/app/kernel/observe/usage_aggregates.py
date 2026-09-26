""" usage_aggregates

Daily usage aggregates, kept by two writers that must agree.

The ``cost.recorded`` consumer adds each usage fact to its day's row as it
arrives. The reconciler rebuilds a whole day from ``run_cost_entries``, the
authoritative ledger, which repairs anything the consumer missed. Both take an
advisory lock on the workspace day, and the rebuild claims the consumer
checkpoint of every fact it counted, so a fact is never added twice: a late
event for a rebuilt day finds its checkpoint taken and is skipped.

Both derive a fact's dimensions with one function, so an incremental total and
a rebuilt one are the same numbers.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, delete, distinct, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now
from app.kernel.events.checkpoint import try_claim_consumer_slot
from app.kernel.runtime.common.advisory_lock import acquire_xact_lock
from app.kernel.runtime.db.models.events import (
    EventConsumerCheckpoint,
    EventOutbox,
    generate_checkpoint_id,
)
from app.kernel.runtime.db.models.runs import Run, RunCostEntry
from app.kernel.runtime.db.models.usage import UsageDailyAggregate

logger = logging.getLogger(__name__)

CONSUMER_NAME = "observe.usage.daily"
LOCK_NAMESPACE = "usage_daily_aggregate"
REHEARSAL_SOURCE = "rehearsal"


@dataclass(frozen=True)
class UsageDimensions:
    tenant_id: str
    workspace_id: str
    day: date
    source: str
    user_id: str
    api_key_id: str
    provider_slug: str
    model_ref: str
    operation: str
    currency: str


@dataclass
class UsageAmounts:
    call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    amount: Decimal = Decimal("0")

    def add(self, other: UsageAmounts) -> None:
        self.call_count += other.call_count
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.amount += other.amount


def cost_event_id(entry_id: str) -> str:
    """The outbox event id the trace writer gives a usage fact."""
    return f"evt_cost_{entry_id}"


def _utc_day(moment: datetime) -> date:
    aware = moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
    return aware.astimezone(UTC).date()


def usage_of(entry: RunCostEntry, run: Run | None) -> tuple[UsageDimensions, UsageAmounts]:
    """The day, dimensions and amounts one usage fact contributes."""
    if run is None:
        source, user_id, api_key_id = "", "", ""
    else:
        source = REHEARSAL_SOURCE if run.sandbox else (run.source or "platform")
        user_id = run.user_id or ""
        api_key_id = run.api_key_id or ""
    dimensions = UsageDimensions(
        tenant_id=entry.tenant_id,
        workspace_id=entry.workspace_id,
        day=_utc_day(entry.created_at),
        source=source,
        user_id=user_id,
        api_key_id=api_key_id,
        provider_slug=entry.provider_slug or "",
        model_ref=entry.model_ref or "",
        operation=entry.operation or "",
        currency=(entry.currency or "") if entry.amount is not None else "",
    )
    prompt = entry.prompt_tokens or 0
    completion = entry.completion_tokens or 0
    amounts = UsageAmounts(
        call_count=1,
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=entry.total_tokens if entry.total_tokens is not None else prompt + completion,
        amount=entry.amount if entry.amount is not None else Decimal("0"),
    )
    return dimensions, amounts


def _insert_for(db: AsyncSession) -> Callable[..., Any]:
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        return postgresql.insert
    if dialect == "sqlite":
        return sqlite.insert
    raise RuntimeError(f"Usage aggregates need an upsert on {dialect}")


async def _add(db: AsyncSession, dimensions: UsageDimensions, amounts: UsageAmounts) -> None:
    table = UsageDailyAggregate.__table__  # type: ignore[attr-defined]
    now = utc_now()
    statement = _insert_for(db)(table).values(
        id=f"uda_{generate_ulid()}",
        **dimensions.__dict__,
        call_count=amounts.call_count,
        prompt_tokens=amounts.prompt_tokens,
        completion_tokens=amounts.completion_tokens,
        total_tokens=amounts.total_tokens,
        amount=amounts.amount,
        updated_at=now,
    )
    excluded = statement.excluded
    await db.exec(
        statement.on_conflict_do_update(
            index_elements=[
                "tenant_id",
                "workspace_id",
                "day",
                "source",
                "user_id",
                "api_key_id",
                "provider_slug",
                "model_ref",
                "operation",
                "currency",
            ],
            set_={
                "call_count": table.c.call_count + excluded.call_count,
                "prompt_tokens": table.c.prompt_tokens + excluded.prompt_tokens,
                "completion_tokens": table.c.completion_tokens + excluded.completion_tokens,
                "total_tokens": table.c.total_tokens + excluded.total_tokens,
                "amount": table.c.amount + excluded.amount,
                "updated_at": excluded.updated_at,
            },
        )
    )


async def _lock_day(db: AsyncSession, tenant_id: str, workspace_id: str, day: date) -> None:
    await acquire_xact_lock(db, LOCK_NAMESPACE, tenant_id, workspace_id, day.isoformat())


async def handle_cost_recorded_usage(db: AsyncSession, row: EventOutbox) -> None:
    """Add one usage fact to its day's aggregate, exactly once."""
    entry_id = (row.payload_json or {}).get("cost_entry_id")
    if not entry_id:
        return
    entry = await db.get(RunCostEntry, str(entry_id))
    if entry is None:
        return
    run = await db.get(Run, entry.run_id)
    dimensions, amounts = usage_of(entry, run)
    # The lock comes before the checkpoint: a rebuild of this day holds it
    # while it claims checkpoints, so the two never both count this fact.
    await _lock_day(db, dimensions.tenant_id, dimensions.workspace_id, dimensions.day)
    if not await try_claim_consumer_slot(
        db, consumer_name=CONSUMER_NAME, event_id=row.event_id, result="usage_daily"
    ):
        return
    await _add(db, dimensions, amounts)


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


async def rebuild_usage_day(db: AsyncSession, tenant_id: str, workspace_id: str, day: date) -> int:
    """Recompute one workspace day from the cost ledger; returns facts counted.

    The caller commits. The day's rows are replaced, and the consumer
    checkpoint of every counted fact is claimed so a late event cannot add it
    again.
    """
    await _lock_day(db, tenant_id, workspace_id, day)
    start, end = _day_bounds(day)
    entries = list(
        (
            await db.exec(
                select(RunCostEntry).where(
                    and_(
                        RunCostEntry.tenant_id == tenant_id,
                        RunCostEntry.workspace_id == workspace_id,
                        RunCostEntry.created_at >= start,
                        RunCostEntry.created_at < end,
                    )
                )
            )
        ).scalars()
    )
    run_ids = {entry.run_id for entry in entries}
    runs: dict[str, Run] = {}
    if run_ids:
        for run in (await db.exec(select(Run).where(Run.id.in_(run_ids)))).scalars():
            runs[run.id] = run

    totals: dict[UsageDimensions, UsageAmounts] = {}
    for entry in entries:
        dimensions, amounts = usage_of(entry, runs.get(entry.run_id))
        if dimensions.day != day:
            continue
        totals.setdefault(dimensions, UsageAmounts()).add(amounts)

    await db.exec(
        delete(UsageDailyAggregate).where(
            and_(
                UsageDailyAggregate.tenant_id == tenant_id,
                UsageDailyAggregate.workspace_id == workspace_id,
                UsageDailyAggregate.day == day,
            )
        )
    )
    for dimensions, amounts in totals.items():
        await _add(db, dimensions, amounts)

    if entries:
        checkpoints = _insert_for(db)(EventConsumerCheckpoint.__table__).values(  # type: ignore[attr-defined]
            [
                {
                    "id": generate_checkpoint_id(),
                    "consumer_name": CONSUMER_NAME,
                    "event_id": cost_event_id(entry.id),
                    "result": "usage_daily_rebuild",
                    "processed_at": utc_now(),
                }
                for entry in entries
            ]
        )
        await db.exec(checkpoints.on_conflict_do_nothing(index_elements=["consumer_name", "event_id"]))
    return len(entries)


async def workspaces_with_usage(db: AsyncSession, day: date) -> list[tuple[str, str]]:
    """Every (tenant, workspace) that recorded usage on ``day``."""
    start, end = _day_bounds(day)
    rows = await db.exec(
        select(distinct(RunCostEntry.tenant_id), RunCostEntry.workspace_id).where(
            and_(RunCostEntry.created_at >= start, RunCostEntry.created_at < end)
        )
    )
    return [(str(tenant_id), str(workspace_id)) for tenant_id, workspace_id in rows.all()]

class UsageAggregateReconciler:
    """Rebuilds the previous UTC day's aggregates from the cost ledger, once a day.

    Several processes may run it; rebuilds of one workspace day serialize on
    the day lock and replace rather than add, so running twice is harmless.
    """

    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.session_factory = session_factory
        self.clock = clock
        self.last_rebuilt: date | None = None

    async def rebuild_day(self, day: date) -> int:
        """Rebuild every workspace that recorded usage on ``day``."""
        async with self.session_factory() as db:
            scopes = await workspaces_with_usage(db, day)
        counted = 0
        for tenant_id, workspace_id in scopes:
            async with self.session_factory() as db:
                counted += await rebuild_usage_day(db, tenant_id, workspace_id, day)
                await db.commit()
        return counted

    async def reconcile_once(self) -> int | None:
        """Rebuild yesterday if this process has not yet; None when nothing ran."""
        yesterday = (self.clock() - timedelta(days=1)).astimezone(UTC).date()
        if self.last_rebuilt == yesterday:
            return None
        counted = await self.rebuild_day(yesterday)
        self.last_rebuilt = yesterday
        logger.info("Usage aggregates rebuilt", extra={"day": yesterday.isoformat(), "facts": counted})
        return counted

    async def run_loop(self, *, interval_seconds: float = 3600.0) -> None:
        while True:
            try:
                await self.reconcile_once()
            except Exception:
                logger.exception("Usage aggregate reconciliation failed")
            await asyncio.sleep(max(60.0, interval_seconds))
