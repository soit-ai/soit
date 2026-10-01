"""PostgreSQL and Redis contract: budget holds across processes.

Each simulated process has its own engine, its own Redis client and its own
in-process fallback, as two API replicas would. Calls are admitted on their
own sessions, at the same time, against one hard-stop budget near its limit:
the shared Redis script must admit exactly the calls the headroom pays for, a
failed call's hold must be released for the other process as soon as its run
ends, and without Redis each process keeps only its own callers within the
limit (the documented overshoot of about one call per replica).

Requires ``DATABASE_URL`` pointing at PostgreSQL and ``SOIT_TEST_REDIS_URL``.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
import redis.asyncio as redis_async
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import BudgetExhaustedError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run, RunCostEntry
from app.modules.billing.application import budget_holds
from app.modules.billing.application.budgets import BudgetGuard
from app.modules.billing.domain.models import Budget
from app.modules.billing.infra.reservations import (
    LocalBudgetReservations,
    RedisBudgetReservations,
)

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

CALLS_PER_PROCESS = 6


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("DATABASE_URL does not point to PostgreSQL")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _redis_url() -> str:
    url = os.environ.get("SOIT_TEST_REDIS_URL", "")
    if not url:
        pytest.skip("SOIT_TEST_REDIS_URL is not set")
    return url


@dataclass
class Process:
    """One API replica: its own connection pool, Redis client and fallback."""

    engine: AsyncEngine
    redis: redis_async.Redis
    reservations: RedisBudgetReservations


@dataclass
class Scope:
    ctx: RequestContext
    budget_ids: list[str]


async def _process(redis_url: str) -> Process:
    engine = create_async_engine(
        _database_url(),
        connect_args={"options": "-c timezone=UTC"},
        pool_size=CALLS_PER_PROCESS + 2,
    )
    client = redis_async.Redis.from_url(redis_url, socket_connect_timeout=0.5)
    return Process(engine, client, RedisBudgetReservations(client, fallback=LocalBudgetReservations()))


@pytest_asyncio.fixture
async def processes() -> AsyncIterator[tuple[Process, Process]]:
    url = _redis_url()
    probe = redis_async.Redis.from_url(url)
    try:
        await probe.ping()
    except Exception as exc:
        pytest.skip(f"Redis at SOIT_TEST_REDIS_URL is unreachable: {exc}")
    finally:
        await probe.aclose()
    first, second = await _process(url), await _process(url)
    yield first, second
    for process in (first, second):
        await process.redis.aclose()
        await process.engine.dispose()


@pytest_asyncio.fixture
async def scope(processes: tuple[Process, Process]) -> AsyncIterator[Scope]:
    token = uuid4().hex
    ctx = RequestContext(
        tenant_id=f"pg-holds-tenant-{token}",
        workspace_id=f"pg-holds-workspace-{token}",
        user_id="u_holds",
        request_id=token,
        tenant_role="Owner",
        workspace_role="Owner",
    )
    scope = Scope(ctx, [])
    yield scope
    engine, client = processes[0].engine, processes[0].redis
    async with AsyncSession(engine) as db:
        await db.exec(delete(Budget).where(Budget.tenant_id == ctx.tenant_id))
        await db.exec(delete(RunCostEntry).where(RunCostEntry.tenant_id == ctx.tenant_id))
        await db.exec(delete(Run).where(Run.tenant_id == ctx.tenant_id))
        await db.commit()
    for budget_id in scope.budget_ids:
        await client.delete(f"budget:inflight:{budget_id}")


async def _seed(engine: AsyncEngine, scope: Scope, *, amount: str, spent_calls: int) -> str:
    """A daily hard-stop budget with ``spent_calls`` calls of 1 USD already spent today."""
    ctx = scope.ctx
    run_id = f"run_spent_{uuid4().hex}"
    async with AsyncSession(engine) as db:
        budget = Budget(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            name="Team",
            amount=Decimal(amount),
            currency="USD",
            period="day",
            hard_stop=True,
            created_by=ctx.user_id,
        )
        db.add(budget)
        db.add(
            Run(
                id=run_id,
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                user_id=ctx.user_id,
                mode="gateway",
                status="succeeded",
                started_at=utc_now(),
            )
        )
        for _ in range(spent_calls):
            db.add(
                RunCostEntry(
                    run_id=run_id,
                    tenant_id=ctx.tenant_id,
                    workspace_id=ctx.workspace_id,
                    billing_basis="tokens",
                    billed_quantity=Decimal(1),
                    currency="USD",
                    amount=Decimal("1"),
                    source_port="llm",
                )
            )
        budget_id = budget.id
        await db.commit()
    scope.budget_ids.append(budget_id)
    return budget_id


async def _open_run(engine: AsyncEngine, ctx: RequestContext) -> str:
    run_id = f"run_call_{uuid4().hex}"
    async with AsyncSession(engine) as db:
        db.add(
            Run(
                id=run_id,
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                user_id=ctx.user_id,
                mode="gateway",
                status="running",
                started_at=utc_now(),
            )
        )
        await db.commit()
    return run_id


async def _drain_releases() -> None:
    while budget_holds._RELEASES:
        await asyncio.gather(*list(budget_holds._RELEASES))


@pytest.mark.asyncio
async def test_two_processes_admit_exactly_what_the_headroom_pays_for(processes, scope) -> None:
    first, second = processes
    # 10 USD a day, 4 spent at 1 USD a call: six more calls fit.
    budget_id = await _seed(first.engine, scope, amount="10", spent_calls=4)
    barrier = asyncio.Barrier(2 * CALLS_PER_PROCESS)
    sessions: list[AsyncSession] = []

    async def call(process: Process) -> str:
        db = AsyncSession(process.engine)
        sessions.append(db)
        guard = BudgetGuard(db, scope.ctx, reservations=process.reservations)
        await barrier.wait()
        try:
            await guard.check(operation="chat", run_id=None)
        except BudgetExhaustedError as refused:
            return str(refused.details["reason"])
        return "admitted"

    try:
        outcomes = await asyncio.gather(
            *(call(process) for process in (first, second) for _ in range(CALLS_PER_PROCESS))
        )
        held = await first.redis.zcard(f"budget:inflight:{budget_id}")
    finally:
        for db in sessions:
            await db.close()

    assert outcomes.count("admitted") == 6
    assert outcomes.count("reserved") == 6
    assert held == 6


@pytest.mark.asyncio
async def test_a_failed_calls_hold_is_freed_for_the_other_process_when_its_run_ends(
    processes, scope
) -> None:
    first, second = processes
    # 5 USD a day, 4 spent: one call fits.
    budget_id = await _seed(first.engine, scope, amount="5", spent_calls=4)
    run_id = await _open_run(first.engine, scope.ctx)

    async with AsyncSession(first.engine) as db_first:
        await BudgetGuard(db_first, scope.ctx, reservations=first.reservations).check(
            operation="chat", run_id=run_id
        )
        await db_first.commit()

        async with AsyncSession(second.engine) as db_second:
            with pytest.raises(BudgetExhaustedError) as refused:
                await BudgetGuard(db_second, scope.ctx, reservations=second.reservations).check(
                    operation="chat", run_id=None
                )
            assert refused.value.details["reason"] == "reserved"

        # The call fails before the provider answers: no cost, and its run ends.
        run = await db_first.get(Run, run_id)
        assert run is not None
        run.status = "failed"
        await db_first.commit()
        await _drain_releases()

    assert await second.redis.zcard(f"budget:inflight:{budget_id}") == 0
    async with AsyncSession(second.engine) as db_second:
        await BudgetGuard(db_second, scope.ctx, reservations=second.reservations).check(
            operation="chat", run_id=None
        )


@pytest.mark.asyncio
async def test_without_redis_each_process_holds_only_its_own_callers(processes, scope) -> None:
    first, _ = processes
    budget_id = await _seed(first.engine, scope, amount="5", spent_calls=4)
    unreachable = redis_async.Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    replicas = [
        RedisBudgetReservations(unreachable, fallback=LocalBudgetReservations()) for _ in range(2)
    ]
    outcomes: list[str] = []
    try:
        for reservations in (replicas[0], replicas[0], replicas[1]):
            async with AsyncSession(first.engine) as db:
                try:
                    await BudgetGuard(db, scope.ctx, reservations=reservations).check(
                        operation="chat", run_id=None
                    )
                    outcomes.append("admitted")
                except BudgetExhaustedError as refused:
                    outcomes.append(str(refused.details["reason"]))
                # Closing the session leaves the hold pending: the call is
                # still running when the next one arrives.
    finally:
        await unreachable.aclose()

    # One call fits. The first replica keeps its own second caller out, but the
    # second replica cannot see the first's hold: one call over, per replica.
    assert outcomes == ["admitted", "reserved", "admitted"]
    assert replicas[0].fallback.held(budget_id) == 1
    assert replicas[1].fallback.held(budget_id) == 1
