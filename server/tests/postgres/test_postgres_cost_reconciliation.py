"""PostgreSQL contract: the cost reconciliation queries read the JSON pricing snapshot.

The pricing status and the unpriced reason come from ``pricing_snapshot_json``,
a ``json`` column on PostgreSQL; the day grouping uses the server's ``date()``.
SQLite runs the API tests; this pins the same answers on PostgreSQL.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run, RunCostEntry
from app.kernel.runtime.runs.cost_queries import CostEntryFilter, CostLedgerQueries

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest_asyncio.fixture
async def postgres_engine() -> AsyncEngine:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        pytest.skip("DATABASE_URL does not point to PostgreSQL")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_async_engine(database_url, connect_args={"options": "-c timezone=UTC"})
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def scope(postgres_engine: AsyncEngine):
    token = uuid4().hex
    tenant_id = f"pg-recon-tenant-{token}"
    workspace_id = f"pg-recon-workspace-{token}"
    yield tenant_id, workspace_id
    async with AsyncSession(postgres_engine) as db:
        await db.exec(delete(RunCostEntry).where(RunCostEntry.tenant_id == tenant_id))
        await db.exec(delete(Run).where(Run.tenant_id == tenant_id))
        await db.commit()


@pytest.mark.asyncio
async def test_statuses_reasons_and_day_groups_on_postgres(postgres_engine: AsyncEngine, scope) -> None:
    tenant_id, workspace_id = scope
    day_one = utc_now().replace(hour=10, minute=0, second=0, microsecond=0) - timedelta(days=2)
    day_two = day_one + timedelta(days=1)
    run_id = f"run_{uuid4().hex}"

    def entry(at, amount, currency, snapshot):
        return RunCostEntry(
            run_id=run_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            billing_basis="tokens",
            billed_quantity=Decimal(10),
            currency=currency,
            amount=None if amount is None else Decimal(amount),
            pricing_snapshot_json=snapshot,
            model_ref="model:openai:gpt-5.1",
            total_tokens=10,
            created_at=at,
        )

    async with AsyncSession(postgres_engine) as db:
        db.add(
            Run(
                id=run_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                user_id="u_pg",
                api_key_id="key_pg",
                source="gateway",
                mode="agent",
                kind="agent",
                status="succeeded",
                started_at=day_one,
            )
        )
        db.add(entry(day_one, "1.25", "USD", {"priced": True}))
        db.add(entry(day_one, "0.75", "USD", {"priced": True, "usage_estimated": True}))
        db.add(entry(day_two, "0", "USD", {"priced": True}))
        db.add(entry(day_two, None, None, {"priced": False, "reason": "image_variant_not_priced"}))
        await db.commit()

    ctx = RequestContext(tenant_id=tenant_id, workspace_id=workspace_id, user_id="u_pg")
    async with AsyncSession(postgres_engine) as db:
        queries = CostLedgerQueries(db, ctx)
        summary = await queries.reconcile(CostEntryFilter(until_inclusive=False), group_by="day")
        estimated = await queries.list_entries(
            CostEntryFilter(pricing_status="estimated", api_key_id="key_pg"), limit=10, offset=0
        )

    assert summary.status_counts == {"priced": 1, "free": 1, "estimated": 1, "unpriced": 1}
    assert summary.amounts == {"USD": Decimal("2.000000")}
    assert summary.estimated_amounts == {"USD": Decimal("0.750000")}
    assert [(item.reason, item.entry_count) for item in summary.unpriced_reasons] == [
        ("image_variant_not_priced", 1)
    ]
    assert [(row.key, row.currency, row.entry_count) for row in summary.groups] == [
        (day_one.date().isoformat(), "USD", 2),
        (day_two.date().isoformat(), "USD", 1),
        (day_two.date().isoformat(), None, 1),
    ]
    assert [item.pricing_status for item in estimated] == ["estimated"]
    assert estimated[0].api_key_id == "key_pg"
