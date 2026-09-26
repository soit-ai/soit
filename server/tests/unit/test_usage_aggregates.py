"""Daily usage aggregates: incremental and rebuilt totals are the same numbers."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlmodel import select

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.observe.usage_aggregates import (
    UsageAggregateReconciler,
    handle_cost_recorded_usage,
    rebuild_usage_day,
)
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.usage import UsageDailyAggregate
from app.kernel.runtime.runs.writer import TraceWriter

TODAY = utc_now().date()


async def _record(async_db, ctx: RequestContext, *, source: str = "gateway", sandbox: bool = False) -> None:
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run("gateway", source=source, sandbox=sandbox)
    for prompt, completion, amount in ((10, 5, "0.0015"), (20, 10, "0.0030")):
        await writer.record_cost(
            run_id=run.id,
            step_id=None,
            billing_basis="tokens",
            billed_quantity=prompt + completion,
            currency="USD",
            amount=Decimal(amount),
            provider_slug="openai-main",
            model_ref="model:openai-main:gpt-live",
            operation="chat",
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
        )
    await async_db.commit()


async def _cost_events(async_db) -> list[EventOutbox]:
    rows = await async_db.exec(select(EventOutbox).where(EventOutbox.event_type == "cost.recorded"))
    return list(rows.all())


async def _totals(async_db) -> list[tuple]:
    rows = (await async_db.exec(select(UsageDailyAggregate))).all()
    return sorted(
        (
            row.day,
            row.source,
            row.user_id,
            row.api_key_id,
            row.model_ref,
            row.operation,
            row.currency,
            row.call_count,
            row.prompt_tokens,
            row.completion_tokens,
            row.total_tokens,
            Decimal(str(row.amount)).normalize(),
        )
        for row in rows
    )


@pytest.fixture
def keyed(ctx: RequestContext) -> RequestContext:
    return replace(ctx, api_key_id="key_usage")


@pytest.mark.asyncio
async def test_each_fact_is_counted_once_per_day_and_dimension(async_db, keyed) -> None:
    await _record(async_db, keyed)
    events = await _cost_events(async_db)

    for event in [*events, events[0]]:
        await handle_cost_recorded_usage(async_db, event)
    await async_db.commit()

    assert await _totals(async_db) == [
        (
            TODAY,
            "gateway",
            keyed.user_id,
            "key_usage",
            "model:openai-main:gpt-live",
            "chat",
            "USD",
            2,
            30,
            15,
            45,
            Decimal("0.0045"),
        )
    ]


@pytest.mark.asyncio
async def test_a_rebuilt_day_equals_the_incremental_one(async_db, keyed) -> None:
    await _record(async_db, keyed)
    await _record(async_db, keyed, source="platform")
    for event in await _cost_events(async_db):
        await handle_cost_recorded_usage(async_db, event)
    await async_db.commit()
    incremental = await _totals(async_db)

    counted = await rebuild_usage_day(async_db, keyed.tenant_id, keyed.workspace_id, TODAY)
    await async_db.commit()

    assert counted == 4
    assert await _totals(async_db) == incremental


@pytest.mark.asyncio
async def test_a_late_event_after_a_rebuild_is_not_counted_again(async_db, keyed) -> None:
    await _record(async_db, keyed)
    await rebuild_usage_day(async_db, keyed.tenant_id, keyed.workspace_id, TODAY)
    await async_db.commit()
    rebuilt = await _totals(async_db)

    for event in await _cost_events(async_db):
        await handle_cost_recorded_usage(async_db, event)
    await async_db.commit()

    assert await _totals(async_db) == rebuilt
    assert rebuilt[0][7] == 2


@pytest.mark.asyncio
async def test_rehearsal_runs_are_kept_apart(async_db, keyed) -> None:
    await _record(async_db, keyed, sandbox=True)
    for event in await _cost_events(async_db):
        await handle_cost_recorded_usage(async_db, event)
    await async_db.commit()

    assert {row[1] for row in await _totals(async_db)} == {"rehearsal"}


@pytest.mark.asyncio
async def test_the_reconciler_rebuilds_yesterday_once(async_db, keyed) -> None:
    await _record(async_db, keyed)
    tomorrow = datetime.combine(TODAY + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    reconciler = UsageAggregateReconciler(lambda: async_db, clock=lambda: tomorrow + timedelta(hours=2))

    assert await reconciler.reconcile_once() == 2
    assert await reconciler.reconcile_once() is None
    assert [row[7] for row in await _totals(async_db)] == [2]
