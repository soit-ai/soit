"""Budgets: spend per period and scope, hard stops, reservations and thresholds."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlmodel import select

from app.kernel.commons.errors import BudgetExhaustedError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run, RunCostEntry
from app.kernel.runtime.db.models.usage import UsageDailyAggregate
from app.modules.billing.application.budgets import (
    BudgetGuard,
    CompositeCreditGuard,
    budget_period,
    budget_spend,
)
from app.modules.billing.domain.models import Budget
from app.modules.billing.events import BUDGET_THRESHOLD_REACHED
from app.modules.billing.handlers.on_budget_thresholds import (
    handle_cost_recorded_budget,
)

NOW = utc_now()


class _Reservations:
    def __init__(self, in_flight: int = 0) -> None:
        self.count = in_flight
        self.reserved: list[str] = []

    async def in_flight(self, budget_id: str) -> int:
        return self.count

    async def reserve(self, budget_id: str) -> None:
        self.reserved.append(budget_id)


class _Recorder:
    def __init__(self) -> None:
        self.blocks: list[dict[str, Any]] = []

    async def record_block(self, ctx: RequestContext, *, details: dict[str, Any]) -> None:
        self.blocks.append(details)


def _budget(ctx: RequestContext, **fields: Any) -> Budget:
    values: dict[str, Any] = {
        "tenant_id": ctx.tenant_id,
        "workspace_id": ctx.workspace_id,
        "name": "Team",
        "amount": Decimal("10"),
        "currency": "USD",
        "created_by": ctx.user_id,
        **fields,
    }
    return Budget(**values)


async def _cost(
    async_db,
    ctx: RequestContext,
    amount: str,
    *,
    run_id: str = "run_budget",
    user_id: str | None = None,
    api_key_id: str | None = None,
    agent_id: str | None = None,
) -> RunCostEntry:
    if await async_db.get(Run, run_id) is None:
        async_db.add(
            Run(
                id=run_id,
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                user_id=user_id or ctx.user_id,
                api_key_id=api_key_id,
                mode="agent" if agent_id else "gateway",
                subject_kind="agent" if agent_id else None,
                subject_id=agent_id,
                status="succeeded",
            )
        )
    entry = RunCostEntry(
        run_id=run_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        billing_basis="tokens",
        billed_quantity=Decimal(1),
        currency="USD",
        amount=Decimal(amount),
    )
    async_db.add(entry)
    await async_db.commit()
    return entry


def test_periods_are_utc_days_and_months() -> None:
    moment = datetime(2026, 12, 31, 23, 30, tzinfo=UTC)

    assert budget_period("day", moment).start == date(2026, 12, 31)
    month = budget_period("month", moment)
    assert (month.start, month.end) == (date(2026, 12, 1), date(2027, 1, 1))
    assert month.resets_at == datetime(2027, 1, 1, tzinfo=UTC)


@pytest.mark.asyncio
async def test_spend_joins_past_aggregates_and_todays_ledger(async_db, ctx) -> None:
    today = NOW.date()
    earlier = today.replace(day=1) if today.day > 1 else today
    if earlier < today:
        async_db.add(
            UsageDailyAggregate(
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                day=earlier,
                user_id=ctx.user_id,
                currency="USD",
                call_count=3,
                amount=Decimal("4"),
            )
        )
    await _cost(async_db, ctx, "1.5")

    spend = await budget_spend(async_db, _budget(ctx), NOW)

    expected = Decimal("5.5") if earlier < today else Decimal("1.5")
    assert spend.spent == expected
    other_currency = await budget_spend(async_db, _budget(ctx, currency="EUR"), NOW)
    assert other_currency.spent == 0


@pytest.mark.asyncio
async def test_key_and_agent_budgets_see_only_their_own_spend(async_db, ctx) -> None:
    await _cost(async_db, ctx, "2", run_id="run_key", api_key_id="key_1")
    await _cost(async_db, ctx, "3", run_id="run_agent", agent_id="agent_1")

    key_spend = await budget_spend(async_db, _budget(ctx, scope_kind="api_key", scope_id="key_1"), NOW)
    agent_spend = await budget_spend(async_db, _budget(ctx, scope_kind="agent", scope_id="agent_1"), NOW)
    workspace_spend = await budget_spend(async_db, _budget(ctx), NOW)

    assert (key_spend.spent, agent_spend.spent, workspace_spend.spent) == (2, 3, 5)


@pytest.mark.asyncio
async def test_a_spent_hard_budget_refuses_with_a_readable_reason(async_db, ctx) -> None:
    async_db.add(_budget(ctx, name="Team monthly"))
    await _cost(async_db, ctx, "10")
    recorder = _Recorder()
    guard = BudgetGuard(async_db, ctx, reservations=_Reservations(), recorder=recorder)

    with pytest.raises(BudgetExhaustedError) as refused:
        await guard.check(operation="chat")

    assert "Team monthly" in refused.value.message
    assert "10 of 10 USD" in refused.value.message
    assert refused.value.details["reason"] == "spent"
    assert refused.value.details["resets_at"].startswith(budget_period("month", NOW).end.isoformat())
    assert recorder.blocks[0]["budget_name"] == "Team monthly"


@pytest.mark.asyncio
async def test_calls_in_flight_hold_the_rest_of_a_budget(async_db, ctx) -> None:
    async_db.add(_budget(ctx))
    for _ in range(4):
        await _cost(async_db, ctx, "2")  # 8 spent, 2 per call on average
    busy = _Reservations(in_flight=1)
    free = _Reservations()

    with pytest.raises(BudgetExhaustedError) as refused:
        await BudgetGuard(async_db, ctx, reservations=busy).check(operation="chat")
    await BudgetGuard(async_db, ctx, reservations=free).check(operation="chat")

    assert refused.value.details["reason"] == "reserved"
    assert len(free.reserved) == 1


@pytest.mark.asyncio
async def test_soft_disabled_and_foreign_budgets_do_not_refuse(async_db, ctx) -> None:
    async_db.add(_budget(ctx, name="Soft", hard_stop=False))
    async_db.add(_budget(ctx, name="Off", status="disabled"))
    async_db.add(_budget(ctx, name="Other key", scope_kind="api_key", scope_id="key_other"))
    await _cost(async_db, ctx, "50")

    await BudgetGuard(async_db, replace(ctx, api_key_id="key_mine")).check(operation="chat")


@pytest.mark.asyncio
async def test_the_composite_guard_stops_at_the_first_refusal() -> None:
    calls: list[str] = []

    class _Refuses:
        async def check(self, *, operation: str, run_id: str | None = None) -> None:
            calls.append("refuses")
            raise BudgetExhaustedError("no")

    class _Allows:
        async def check(self, *, operation: str, run_id: str | None = None) -> None:
            calls.append("allows")

    with pytest.raises(BudgetExhaustedError):
        await CompositeCreditGuard(_Allows(), None, _Refuses(), _Allows()).check(operation="x")
    assert calls == ["allows", "refuses"]


async def _threshold_events(async_db) -> list[EventOutbox]:
    rows = await async_db.exec(
        select(EventOutbox).where(EventOutbox.event_type == BUDGET_THRESHOLD_REACHED)
    )
    return list(rows.all())


def _cost_event(entry: RunCostEntry) -> EventOutbox:
    return EventOutbox(
        event_id=f"evt_cost_{entry.id}",
        event_type="cost.recorded",
        idempotency_key=f"evt_cost_{entry.id}",
        payload_json={"cost_entry_id": entry.id},
    )


@pytest.mark.asyncio
async def test_each_threshold_is_announced_once_per_period(async_db, ctx) -> None:
    async_db.add(_budget(ctx, thresholds_json=[50, 100], hard_stop=False))
    await async_db.commit()

    for amount in ("4", "2", "1", "5"):
        entry = await _cost(async_db, ctx, amount)
        event = _cost_event(entry)
        await handle_cost_recorded_budget(async_db, event)
        await handle_cost_recorded_budget(async_db, event)
        await async_db.commit()

    events = await _threshold_events(async_db)
    assert sorted(event.payload_json["threshold"] for event in events) == [50, 100]
    crossed = {event.payload_json["threshold"]: event.payload_json for event in events}
    assert crossed[50]["spent"].startswith("6")
    assert crossed[100]["spent"].startswith("12")


@pytest.mark.asyncio
async def test_unpriced_usage_raises_no_threshold(async_db, ctx) -> None:
    async_db.add(_budget(ctx, amount=Decimal("1"), thresholds_json=[50]))
    entry = await _cost(async_db, ctx, "0")

    await handle_cost_recorded_budget(async_db, _cost_event(entry))

    assert await _threshold_events(async_db) == []


@pytest.mark.asyncio
async def test_a_day_budget_counts_only_today(async_db, ctx) -> None:
    yesterday = await _cost(async_db, ctx, "3")
    yesterday.created_at = NOW - timedelta(days=1)
    async_db.add(yesterday)
    await async_db.commit()
    await _cost(async_db, ctx, "1")

    spend = await budget_spend(async_db, _budget(ctx, period="day"), NOW)

    assert spend.spent == 1

@pytest.mark.asyncio
async def test_tool_calls_pass_the_spend_guard(ctx) -> None:
    from unittest.mock import AsyncMock

    from app.kernel.ports.tools.policy import ToolPolicyGateway

    class _Refuses:
        async def check(self, *, operation: str, run_id: str | None = None) -> None:
            raise BudgetExhaustedError("Tool budget spent", {"operation": operation})

    tools = AsyncMock()
    gateway = ToolPolicyGateway(gateway=tools, ctx=ctx, enable_egress_check=False, credit_guard=_Refuses())

    with pytest.raises(BudgetExhaustedError) as refused:
        await gateway.invoke("builtin:search", {"q": "x"})

    assert refused.value.details == {"operation": "tool"}
    tools.invoke.assert_not_awaited()
