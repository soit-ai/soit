"""PostgreSQL contract: concurrent consumers and a rebuild count each fact once.

The consumer and the nightly rebuild both write a day's aggregate. Each
contender runs on its own ``AsyncSession`` and is released by a barrier so
their transactions overlap on the server; the per-day advisory lock and the
consumer checkpoints are what keep the totals exact.
"""

from __future__ import annotations

import asyncio
import os
import sys
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.observe.usage_aggregates import (
    CONSUMER_NAME,
    cost_event_id,
    handle_cost_recorded_usage,
    rebuild_usage_day,
)
from app.kernel.runtime.db.models.events import EventConsumerCheckpoint, EventOutbox
from app.kernel.runtime.db.models.runs import Run, RunCostEntry
from app.kernel.runtime.db.models.usage import UsageDailyAggregate

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

FACTS = 12


@pytest_asyncio.fixture
async def postgres_engine() -> AsyncEngine:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        pytest.skip("DATABASE_URL does not point to PostgreSQL")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_async_engine(
        database_url,
        connect_args={"options": "-c timezone=UTC"},
        pool_pre_ping=True,
        pool_size=FACTS + 4,
    )
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def usage_scope(postgres_engine: AsyncEngine):
    token = uuid4().hex
    tenant_id = f"pg-usage-tenant-{token}"
    workspace_id = f"pg-usage-workspace-{token}"
    yield token, tenant_id, workspace_id
    async with AsyncSession(postgres_engine) as db:
        await db.exec(delete(UsageDailyAggregate).where(UsageDailyAggregate.tenant_id == tenant_id))
        await db.exec(delete(RunCostEntry).where(RunCostEntry.tenant_id == tenant_id))
        await db.exec(delete(Run).where(Run.tenant_id == tenant_id))
        await db.exec(
            delete(EventConsumerCheckpoint).where(
                EventConsumerCheckpoint.event_id.like(f"evt_cost_{token}_%")
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_concurrent_consumers_and_a_rebuild_count_each_fact_once(
    postgres_engine: AsyncEngine, usage_scope
) -> None:
    token, tenant_id, workspace_id = usage_scope
    async with AsyncSession(postgres_engine, expire_on_commit=False) as db:
        run = Run(
            id=f"run_{token}",
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            user_id="pg-user",
            mode="gateway",
            status="succeeded",
            source="gateway",
            api_key_id="pg-key",
        )
        db.add(run)
        entries = [
            RunCostEntry(
                id=f"{token}_{index}",
                run_id=run.id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                billing_basis="tokens",
                billed_quantity=Decimal(3),
                currency="USD",
                amount=Decimal("0.001"),
                provider_slug="pg-provider",
                model_ref="model:pg-provider:m",
                operation="chat",
                prompt_tokens=2,
                completion_tokens=1,
                total_tokens=3,
            )
            for index in range(FACTS)
        ]
        db.add_all(entries)
        await db.commit()
    events = [
        EventOutbox(
            event_id=cost_event_id(entry.id),
            event_type="cost.recorded",
            idempotency_key=cost_event_id(entry.id),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            payload_json={"cost_entry_id": entry.id},
        )
        for entry in entries
    ]
    barrier = asyncio.Barrier(FACTS + 1)

    async def consume(event: EventOutbox, *, wait: bool = True) -> None:
        async with AsyncSession(postgres_engine) as db:
            if wait:
                await barrier.wait()
            await handle_cost_recorded_usage(db, event)
            await db.commit()

    async def rebuild() -> None:
        async with AsyncSession(postgres_engine) as db:
            await barrier.wait()
            await rebuild_usage_day(db, tenant_id, workspace_id, utc_now().date())
            await db.commit()

    await asyncio.wait_for(
        asyncio.gather(*(consume(event) for event in events), rebuild()), timeout=60
    )
    for event in events:
        await consume(event, wait=False)

    async with AsyncSession(postgres_engine) as db:
        rows = list(
            (
                await db.exec(
                    select(UsageDailyAggregate).where(UsageDailyAggregate.tenant_id == tenant_id)
                )
            ).scalars()
        )
        claimed = list(
            (
                await db.exec(
                    select(EventConsumerCheckpoint.event_id).where(
                        EventConsumerCheckpoint.consumer_name == CONSUMER_NAME,
                        EventConsumerCheckpoint.event_id.like(f"evt_cost_{token}_%"),
                    )
                )
            ).scalars()
        )

    assert len(rows) == 1
    row = rows[0]
    assert (row.source, row.user_id, row.api_key_id) == ("gateway", "pg-user", "pg-key")
    assert row.call_count == FACTS
    assert row.total_tokens == 3 * FACTS
    assert Decimal(str(row.amount)) == Decimal("0.001") * FACTS
    assert len(claimed) == FACTS
