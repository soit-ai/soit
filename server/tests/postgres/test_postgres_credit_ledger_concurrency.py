"""PostgreSQL-only concurrency contracts for the workspace credit ledger.

Deductions arrive through the outbox and can be consumed by several
dispatchers at once. Each contender here runs on its own ``AsyncSession`` and
is released by an ``asyncio.Barrier`` so the transactions overlap on the
server: the unique ``cost_entry_id`` index and the per-workspace advisory lock
are what keep the ledger exact and the threshold alerts single.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Awaitable, Callable, Sequence
from decimal import Decimal
from typing import TypeVar
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.events import EventConsumerCheckpoint, EventOutbox
from app.modules.billing.application.service import CreditService
from app.modules.billing.domain.models import CreditLedgerEntry
from app.modules.billing.events import CREDIT_BALANCE_LOW
from app.modules.billing.handlers import on_cost_recorded
from app.modules.billing.handlers.on_cost_recorded import (
    CONSUMER_NAME,
    handle_cost_recorded_credit,
)
from app.settings.settings import settings

if sys.platform == "win32":
    # psycopg's async mode refuses the Proactor loop that pytest-asyncio
    # would otherwise create on Windows.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

T = TypeVar("T")

RACE_TIMEOUT_SECONDS = 60


@pytest_asyncio.fixture
async def postgres_engine() -> AsyncEngine:
    """Use only the explicitly configured PostgreSQL acceptance database."""

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        pytest.skip("DATABASE_URL does not point to PostgreSQL")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_async_engine(
        database_url,
        connect_args={"options": "-c timezone=UTC"},
        pool_pre_ping=True,
        pool_size=10,
    )
    if engine.dialect.name != "postgresql":
        await engine.dispose()
        pytest.skip("PostgreSQL dialect is required")
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def ledger_scope(postgres_engine: AsyncEngine):
    """Return a unique tenant/workspace and remove its rows afterwards."""

    token = uuid4().hex
    tenant_id = f"pg-credit-tenant-{token}"
    workspace_id = f"pg-credit-workspace-{token}"
    yield token, tenant_id, workspace_id
    async with AsyncSession(postgres_engine) as db:
        await db.exec(delete(CreditLedgerEntry).where(CreditLedgerEntry.tenant_id == tenant_id))
        await db.exec(delete(EventOutbox).where(EventOutbox.tenant_id == tenant_id))
        await db.exec(
            delete(EventConsumerCheckpoint).where(
                EventConsumerCheckpoint.event_id.like(f"evt_cost_{token}_%")
            )
        )
        await db.commit()


def _session(engine: AsyncEngine) -> AsyncSession:
    return AsyncSession(engine, expire_on_commit=False)


async def _race(
    engine: AsyncEngine,
    contenders: Sequence[Callable[[AsyncSession], Awaitable[T]]],
) -> list[T]:
    barrier = asyncio.Barrier(len(contenders))

    async def run(contender: Callable[[AsyncSession], Awaitable[T]]) -> T:
        async with _session(engine) as db:
            await barrier.wait()
            return await contender(db)

    async with asyncio.timeout(RACE_TIMEOUT_SECONDS):
        return list(await asyncio.gather(*(run(item) for item in contenders)))


def _cost_event(
    token: str,
    tenant_id: str,
    workspace_id: str,
    *,
    suffix: str,
    cost_entry_id: str,
    amount: str,
) -> EventOutbox:
    event_id = f"evt_cost_{token}_{suffix}"
    return EventOutbox(
        event_id=event_id,
        event_type="cost.recorded",
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        idempotency_key=event_id,
        payload_json={
            "cost_entry_id": cost_entry_id,
            "tenant_id": tenant_id,
            "workspace_id": workspace_id,
            "run_id": f"run_{token}",
            "billing_basis": "tokens",
            "amount": amount,
            "currency": "USD",
        },
    )


def _consume(row: EventOutbox) -> Callable[[AsyncSession], Awaitable[None]]:
    async def contender(db: AsyncSession) -> None:
        await handle_cost_recorded_credit(db, row)
        await db.commit()

    return contender


async def _grant(engine: AsyncEngine, tenant_id: str, workspace_id: str, credits: str) -> None:
    ctx = RequestContext(tenant_id=tenant_id, workspace_id=workspace_id, user_id="pg-credit-admin")
    async with _session(engine) as db:
        await CreditService(db, ctx).grant(credits=Decimal(credits), note="contract setup")
        await db.commit()


async def _ledger(engine: AsyncEngine, tenant_id: str) -> list[CreditLedgerEntry]:
    async with _session(engine) as db:
        rows = (
            await db.exec(select(CreditLedgerEntry).where(CreditLedgerEntry.tenant_id == tenant_id))
        ).all()
    return [row if isinstance(row, CreditLedgerEntry) else row[0] for row in rows]


async def _alert_states(engine: AsyncEngine, tenant_id: str) -> list[str]:
    async with _session(engine) as db:
        rows = (
            await db.exec(
                select(EventOutbox).where(
                    EventOutbox.tenant_id == tenant_id,
                    EventOutbox.event_type == CREDIT_BALANCE_LOW,
                )
            )
        ).all()
    events = [row if isinstance(row, EventOutbox) else row[0] for row in rows]
    return sorted(str((event.payload_json or {}).get("state")) for event in events)


@pytest.fixture(autouse=True)
def _credit_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "credit_rates_json", '{"USD": "1000"}')
    monkeypatch.setattr(settings, "credit_low_balance_threshold", 100.0)


@pytest.fixture
def widen_balance_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hold each consumer after its balance read until a competitor reads too.

    Round trips are fast enough that two overlapping consumers rarely read the
    balance at the same moment by chance. Here every reader waits up to half a
    second for another reader, so without serialisation both read the same
    balance. Under the advisory lock the competitor is blocked before its
    read, the wait times out, and the first consumer books alone.
    """

    original = on_cost_recorded._workspace_balance
    readers = 0
    another_reader = asyncio.Event()

    async def held_balance(db: AsyncSession, tenant_id: str, workspace_id: str) -> Decimal:
        nonlocal readers
        balance = await original(db, tenant_id, workspace_id)
        readers += 1
        if readers >= 2:
            another_reader.set()
        try:
            await asyncio.wait_for(another_reader.wait(), timeout=0.5)
        except TimeoutError:
            pass
        return balance

    monkeypatch.setattr(on_cost_recorded, "_workspace_balance", held_balance)


@pytest.mark.asyncio
async def test_concurrent_redelivery_of_one_event_books_once(
    postgres_engine: AsyncEngine, ledger_scope
) -> None:
    """Two dispatchers consuming the same event produce exactly one row."""

    token, tenant_id, workspace_id = ledger_scope
    contenders = [
        _consume(
            _cost_event(
                token, tenant_id, workspace_id, suffix="dup", cost_entry_id=f"ce_{token}", amount="0.1"
            )
        )
        for _ in range(4)
    ]

    await _race(postgres_engine, contenders)

    rows = await _ledger(postgres_engine, tenant_id)
    assert len(rows) == 1
    assert rows[0].credits_delta == Decimal("-100.000000")
    async with _session(postgres_engine) as db:
        claims = (
            await db.exec(
                select(func.count())
                .select_from(EventConsumerCheckpoint)
                .where(
                    EventConsumerCheckpoint.consumer_name == CONSUMER_NAME,
                    EventConsumerCheckpoint.event_id == f"evt_cost_{token}_dup",
                )
            )
        ).one()
    assert (claims if isinstance(claims, int) else claims[0]) == 1


@pytest.mark.asyncio
async def test_distinct_events_for_one_cost_entry_book_once(
    postgres_engine: AsyncEngine, ledger_scope
) -> None:
    """A cost entry priced by two different events is still deducted once."""

    token, tenant_id, workspace_id = ledger_scope
    contenders = [
        _consume(
            _cost_event(
                token,
                tenant_id,
                workspace_id,
                suffix=f"retry{index}",
                cost_entry_id=f"ce_{token}",
                amount="0.1",
            )
        )
        for index in range(3)
    ]

    await _race(postgres_engine, contenders)

    rows = await _ledger(postgres_engine, tenant_id)
    assert [row.cost_entry_id for row in rows] == [f"ce_{token}"]


@pytest.mark.asyncio
async def test_parallel_deductions_sum_exactly(postgres_engine: AsyncEngine, ledger_scope) -> None:
    """N concurrent deductions for one workspace neither drop nor double any row."""

    token, tenant_id, workspace_id = ledger_scope
    await _grant(postgres_engine, tenant_id, workspace_id, "100000")
    contenders = [
        _consume(
            _cost_event(
                token,
                tenant_id,
                workspace_id,
                suffix=f"n{index}",
                cost_entry_id=f"ce_{token}_{index}",
                amount="0.013",
            )
        )
        for index in range(8)
    ]

    await _race(postgres_engine, contenders)

    rows = await _ledger(postgres_engine, tenant_id)
    deductions = [row for row in rows if row.kind == "deduction"]
    assert len(deductions) == 8
    balance = sum((row.credits_delta for row in rows), Decimal("0"))
    assert balance == Decimal("100000") - Decimal("13") * 8


@pytest.mark.asyncio
@pytest.mark.usefixtures("widen_balance_window")
async def test_threshold_crossed_concurrently_alerts_once(
    postgres_engine: AsyncEngine, ledger_scope
) -> None:
    """Two deductions that together cross the low threshold alert exactly once.

    From 250 credits, two 100-credit deductions land at 150 and then 50.
    Only the second crosses the 100 threshold; read outside the lock, both
    would see 250 and neither would alert.
    """

    token, tenant_id, workspace_id = ledger_scope
    await _grant(postgres_engine, tenant_id, workspace_id, "250")
    contenders = [
        _consume(
            _cost_event(
                token,
                tenant_id,
                workspace_id,
                suffix=f"low{index}",
                cost_entry_id=f"ce_{token}_low{index}",
                amount="0.1",
            )
        )
        for index in range(2)
    ]

    await _race(postgres_engine, contenders)

    assert await _alert_states(postgres_engine, tenant_id) == ["low"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("widen_balance_window")
async def test_exhaustion_race_reports_low_then_exhausted(
    postgres_engine: AsyncEngine, ledger_scope
) -> None:
    """From 150 credits two 100-credit deductions report low once, exhausted once."""

    token, tenant_id, workspace_id = ledger_scope
    await _grant(postgres_engine, tenant_id, workspace_id, "150")
    contenders = [
        _consume(
            _cost_event(
                token,
                tenant_id,
                workspace_id,
                suffix=f"ex{index}",
                cost_entry_id=f"ce_{token}_ex{index}",
                amount="0.1",
            )
        )
        for index in range(2)
    ]

    await _race(postgres_engine, contenders)

    assert await _alert_states(postgres_engine, tenant_id) == ["exhausted", "low"]
    rows = await _ledger(postgres_engine, tenant_id)
    assert sum((row.credits_delta for row in rows), Decimal("0")) == Decimal("-50")
