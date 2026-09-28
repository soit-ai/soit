"""Budget holds: taken atomically, released when the call's cost is committed."""

from __future__ import annotations

import asyncio
import os
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
import redis.asyncio as redis_async

from app.kernel.commons.errors import BudgetExhaustedError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run, RunCostEntry
from app.modules.billing.application import budget_holds
from app.modules.billing.application.budgets import (
    BudgetGuard,
    HoldGrant,
    HoldRefusal,
    HoldRequest,
    hold_capacity,
    hold_ttl_seconds,
)
from app.modules.billing.domain.models import Budget
from app.modules.billing.infra.reservations import (
    LocalBudgetReservations,
    RedisBudgetReservations,
)
from app.settings.settings import settings


class _Recording(LocalBudgetReservations):
    def __init__(self) -> None:
        super().__init__()
        self.released: list[HoldGrant] = []

    async def release(self, grant: HoldGrant) -> None:
        self.released.append(grant)
        await super().release(grant)


async def _drain_releases() -> None:
    while budget_holds._RELEASES:
        await asyncio.gather(*list(budget_holds._RELEASES))


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


async def _run(async_db, ctx: RequestContext, run_id: str) -> None:
    async_db.add(
        Run(
            id=run_id,
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            mode="gateway",
            status="running",
        )
    )
    await async_db.commit()


def _cost_row(
    ctx: RequestContext, run_id: str, amount: str = "1", *, source_port: str = "llm"
) -> RunCostEntry:
    return RunCostEntry(
        run_id=run_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        billing_basis="tokens",
        billed_quantity=Decimal(1),
        currency="USD",
        amount=Decimal(amount),
        source_port=source_port,
    )


def test_capacity_counts_whole_calls_that_fit() -> None:
    assert hold_capacity(Decimal("5"), Decimal("2")) == 2
    assert hold_capacity(Decimal("4"), Decimal("2")) == 2
    assert hold_capacity(Decimal("1"), Decimal("2")) == 0
    assert hold_capacity(Decimal("5"), Decimal("0")) is None


def test_an_unreleased_hold_outlasts_the_calls_timeout() -> None:
    assert hold_ttl_seconds("chat") > settings.llm_timeout_seconds
    assert hold_ttl_seconds("tool") > settings.llm_timeout_seconds
    assert hold_ttl_seconds("generate_image") > settings.llm_image_timeout_seconds
    assert hold_ttl_seconds("edit_image") > settings.llm_image_timeout_seconds


@pytest.mark.asyncio
async def test_a_full_budget_refuses_and_holds_nothing_elsewhere() -> None:
    holds = LocalBudgetReservations()
    first = await holds.acquire([HoldRequest("b_team", 1), HoldRequest("b_key", None)], ttl_seconds=60)
    second = await holds.acquire([HoldRequest("b_key", None), HoldRequest("b_team", 1)], ttl_seconds=60)

    assert isinstance(first, HoldGrant)
    assert second == HoldRefusal("b_team", 1)
    assert holds.held("b_key") == 1  # the refused call took no hold on the other budget

    await holds.release(first)
    assert (holds.held("b_team"), holds.held("b_key")) == (0, 0)


@pytest.mark.asyncio
async def test_an_unreleased_hold_expires() -> None:
    holds = LocalBudgetReservations()
    await holds.acquire([HoldRequest("b_team", 1)], ttl_seconds=0.01)
    await asyncio.sleep(0.02)

    assert isinstance(await holds.acquire([HoldRequest("b_team", 1)], ttl_seconds=60), HoldGrant)


@pytest.mark.asyncio
async def test_without_redis_holds_are_kept_in_the_process() -> None:
    broken = redis_async.Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    holds = RedisBudgetReservations(broken)
    try:
        first = await holds.acquire([HoldRequest("b_team", 1)], ttl_seconds=60)
        second = await holds.acquire([HoldRequest("b_team", 1)], ttl_seconds=60)

        assert isinstance(first, HoldGrant) and first.backend == "local"
        assert second == HoldRefusal("b_team", 1)
        await holds.release(first)
        assert holds.fallback.held("b_team") == 0
    finally:
        await broken.aclose()


@pytest.mark.asyncio
async def test_a_hold_is_released_once_its_calls_cost_is_committed(async_db, ctx) -> None:
    budget = _budget(ctx)
    async_db.add(budget)
    await _run(async_db, ctx, "run_hold")
    holds = _Recording()

    await BudgetGuard(async_db, ctx, reservations=holds).check(operation="chat", run_id="run_hold")
    assert holds.held(budget.id) == 1

    async_db.add(_cost_row(ctx, "run_hold"))
    await async_db.flush()
    await _drain_releases()
    assert holds.held(budget.id) == 1  # flushed, but other callers cannot read it yet

    await async_db.commit()
    await _drain_releases()
    assert holds.held(budget.id) == 0
    assert len(holds.released) == 1


@pytest.mark.asyncio
async def test_a_call_without_a_cost_keeps_its_hold(async_db, ctx) -> None:
    budget = _budget(ctx)
    async_db.add(budget)
    await _run(async_db, ctx, "run_failed")
    await _run(async_db, ctx, "run_other")
    holds = _Recording()

    await BudgetGuard(async_db, ctx, reservations=holds).check(operation="chat", run_id="run_failed")
    async_db.add(_cost_row(ctx, "run_other"))
    await async_db.commit()
    await _drain_releases()

    assert holds.held(budget.id) == 1
    assert holds.released == []


@pytest.mark.asyncio
async def test_a_storage_cost_does_not_release_a_model_calls_hold(async_db, ctx) -> None:
    budget = _budget(ctx)
    async_db.add(budget)
    await _run(async_db, ctx, "run_image")
    holds = _Recording()

    await BudgetGuard(async_db, ctx, reservations=holds).check(operation="generate_image", run_id="run_image")
    async_db.add(_cost_row(ctx, "run_image", "0", source_port="storage"))  # the artifact, stored mid-call
    await async_db.commit()
    await _drain_releases()
    assert holds.held(budget.id) == 1

    async_db.add(_cost_row(ctx, "run_image", source_port="llm"))
    await async_db.commit()
    await _drain_releases()
    assert holds.held(budget.id) == 0


@pytest.mark.asyncio
async def test_a_tool_calls_cost_releases_its_hold(async_db, ctx) -> None:
    budget = _budget(ctx)
    async_db.add(budget)
    await _run(async_db, ctx, "run_tool")
    holds = _Recording()

    await BudgetGuard(async_db, ctx, reservations=holds).check(operation="tool", run_id="run_tool")
    async_db.add(_cost_row(ctx, "run_tool", source_port="tools"))
    await async_db.commit()
    await _drain_releases()

    assert holds.held(budget.id) == 0


@pytest.mark.asyncio
async def test_a_run_that_ends_releases_the_holds_its_failed_calls_kept(async_db, ctx) -> None:
    budget = _budget(ctx)
    async_db.add(budget)
    await _run(async_db, ctx, "run_ends")
    holds = _Recording()
    guard = BudgetGuard(async_db, ctx, reservations=holds)

    # Two calls admitted; both fail before the provider answers, so no cost.
    await guard.check(operation="chat", run_id="run_ends")
    await guard.check(operation="chat", run_id="run_ends")
    await async_db.commit()
    await _drain_releases()
    assert holds.held(budget.id) == 2

    run = await async_db.get(Run, "run_ends")
    assert run is not None
    run.status = "failed"
    await async_db.commit()
    await _drain_releases()

    assert holds.held(budget.id) == 0
    assert len(holds.released) == 2


@pytest.mark.asyncio
async def test_a_run_still_going_keeps_its_holds(async_db, ctx) -> None:
    budget = _budget(ctx)
    async_db.add(budget)
    await _run(async_db, ctx, "run_going")
    holds = _Recording()

    await BudgetGuard(async_db, ctx, reservations=holds).check(operation="chat", run_id="run_going")
    run = await async_db.get(Run, "run_going")
    assert run is not None
    run.status = "running"
    await async_db.commit()
    await _drain_releases()

    assert holds.held(budget.id) == 1


@pytest.mark.asyncio
async def test_a_run_releases_one_hold_per_costed_call(async_db, ctx) -> None:
    budget = _budget(ctx)
    async_db.add(budget)
    await _run(async_db, ctx, "run_two_calls")
    holds = _Recording()
    guard = BudgetGuard(async_db, ctx, reservations=holds)

    await guard.check(operation="chat", run_id="run_two_calls")
    await guard.check(operation="chat", run_id="run_two_calls")
    async_db.add(_cost_row(ctx, "run_two_calls"))
    await async_db.commit()
    await _drain_releases()

    assert holds.held(budget.id) == 1


@pytest.mark.asyncio
async def test_a_rolled_back_cost_releases_its_hold(async_db, ctx) -> None:
    budget = _budget(ctx)
    async_db.add(budget)
    await _run(async_db, ctx, "run_rolled_back")
    holds = _Recording()

    await BudgetGuard(async_db, ctx, reservations=holds).check(operation="chat", run_id="run_rolled_back")
    budget_id = budget.id
    async_db.add(_cost_row(ctx, "run_rolled_back"))
    await async_db.flush()
    await async_db.rollback()
    await _drain_releases()

    assert holds.held(budget_id) == 0


@pytest.mark.asyncio
async def test_a_released_hold_frees_the_slot_for_the_next_caller(async_db, ctx) -> None:
    budget = _budget(ctx, amount=Decimal("4"))
    async_db.add(budget)
    await _run(async_db, ctx, "run_first")
    await _run(async_db, ctx, "run_second")
    async_db.add(_cost_row(ctx, "run_first", "2"))  # 2 spent, 2 per call: one more call fits
    await async_db.commit()
    holds = _Recording()
    guard = BudgetGuard(async_db, ctx, reservations=holds)

    await guard.check(operation="chat", run_id="run_second")
    with pytest.raises(BudgetExhaustedError) as refused:
        await guard.check(operation="chat", run_id="run_second")
    assert refused.value.details["reason"] == "reserved"

    async_db.add(_cost_row(ctx, "run_second", "1"))
    await async_db.commit()
    await _drain_releases()
    assert holds.held(budget.id) == 0


@pytest_asyncio.fixture
async def redis_client():
    url = os.environ.get("SOIT_TEST_REDIS_URL")
    if not url:
        pytest.skip("SOIT_TEST_REDIS_URL is not set")
    client = redis_async.Redis.from_url(url)
    try:
        await client.ping()
    except Exception as exc:
        await client.aclose()
        pytest.skip(f"Redis at SOIT_TEST_REDIS_URL is unreachable: {exc}")
    yield client
    await client.aclose()


@pytest.mark.asyncio
async def test_redis_holds_are_checked_and_taken_in_one_step(redis_client) -> None:
    team, key = f"b_{uuid4().hex}", f"b_{uuid4().hex}"
    holds = RedisBudgetReservations(redis_client)
    try:
        callers = await asyncio.gather(
            *(holds.acquire([HoldRequest(key, None), HoldRequest(team, 2)], ttl_seconds=60) for _ in range(6))
        )
        granted = [outcome for outcome in callers if isinstance(outcome, HoldGrant)]
        refused = [outcome for outcome in callers if isinstance(outcome, HoldRefusal)]

        assert len(granted) == 2 and all(grant.backend == "redis" for grant in granted)
        assert {outcome.budget_id for outcome in refused} == {team}
        assert await redis_client.zcard(f"budget:inflight:{key}") == 2

        await holds.release(granted[0])
        assert await redis_client.zcard(f"budget:inflight:{team}") == 1
        assert isinstance(await holds.acquire([HoldRequest(team, 2)], ttl_seconds=60), HoldGrant)

        await redis_client.zadd(f"budget:inflight:{team}", {"expired": 1})
        assert isinstance(await holds.acquire([HoldRequest(team, 4)], ttl_seconds=60), HoldGrant)
        assert await redis_client.zscore(f"budget:inflight:{team}", "expired") is None
    finally:
        await redis_client.delete(f"budget:inflight:{team}", f"budget:inflight:{key}")
