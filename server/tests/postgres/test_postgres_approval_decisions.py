"""PostgreSQL-only: concurrent decisions on one approval request.

Each contender decides on its own ``AsyncSession``, released together by a
barrier so the transactions overlap on the server. Exactly one decision is
taken, the request ends in that state, and one resolution event is sent.
"""

from __future__ import annotations

import asyncio
import os
import sys
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import ConflictError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run
from app.modules.observe.application.approval_sweeper import (
    close_approvals_of_ended_runs,
)
from app.modules.observe.application.schemas import ApprovalResolve
from app.modules.observe.application.service import ObserveService
from app.modules.observe.domain.models import ApprovalRequest

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

RACE_TIMEOUT_SECONDS = 60


@pytest_asyncio.fixture
async def postgres_engine() -> AsyncEngine:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        pytest.skip("DATABASE_URL does not point to PostgreSQL")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_async_engine(database_url, connect_args={"options": "-c timezone=UTC"}, pool_size=8)
    if engine.dialect.name != "postgresql":
        await engine.dispose()
        pytest.skip("PostgreSQL dialect is required")
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def ctx(postgres_engine: AsyncEngine):
    token = uuid4().hex
    context = RequestContext(
        tenant_id=f"pg-tenant-{token}",
        workspace_id=f"pg-workspace-{token}",
        user_id="u_owner",
        tenant_role="Owner",
        workspace_role="Owner",
    )
    yield context
    async with AsyncSession(postgres_engine) as db:
        await db.exec(delete(EventOutbox).where(EventOutbox.tenant_id == context.tenant_id))
        await db.exec(delete(ApprovalRequest).where(ApprovalRequest.tenant_id == context.tenant_id))
        await db.commit()


async def _pending(engine: AsyncEngine, ctx: RequestContext) -> str:
    async with AsyncSession(engine, expire_on_commit=False) as db:
        approval = ApprovalRequest(
            tenant_id=ctx.tenant_id,
            workspace_id=ctx.workspace_id,
            run_id=f"run-{uuid4().hex}",
            title="Approve tool call: tool:test:send",
        )
        db.add(approval)
        await db.commit()
        return approval.id


async def _decide_together(engine: AsyncEngine, ctx: RequestContext, approval_id: str, decisions: list[str]) -> list:
    barrier = asyncio.Barrier(len(decisions))

    async def decide(decision: str):
        async with AsyncSession(engine, expire_on_commit=False) as db:
            await barrier.wait()
            try:
                approval = await ObserveService(db, ctx).resolve_approval(approval_id, ApprovalResolve(status=decision))
                return approval.status
            except ConflictError as exc:
                return exc

    async with asyncio.timeout(RACE_TIMEOUT_SECONDS):
        return list(await asyncio.gather(*(decide(item) for item in decisions)))


async def _stored(engine: AsyncEngine, approval_id: str) -> tuple[str, list[str]]:
    async with AsyncSession(engine) as db:
        approval = await db.get(ApprovalRequest, approval_id)
        events = (
            await db.exec(select(EventOutbox.event_type).where(EventOutbox.subject_id == approval_id))
        ).scalars().all()
        return approval.status, sorted(str(event) for event in events if str(event) != "approval.requested")


@pytest.mark.asyncio
async def test_approve_and_reject_together_take_exactly_one(postgres_engine: AsyncEngine, ctx) -> None:
    approval_id = await _pending(postgres_engine, ctx)

    outcomes = await _decide_together(postgres_engine, ctx, approval_id, ["approved", "rejected"])

    taken = [outcome for outcome in outcomes if isinstance(outcome, str)]
    refused = [outcome for outcome in outcomes if isinstance(outcome, ConflictError)]
    assert len(taken) == 1 and len(refused) == 1, outcomes
    stored, events = await _stored(postgres_engine, approval_id)
    assert stored == taken[0]
    assert events == [f"approval.{taken[0]}"]


@pytest.mark.asyncio
async def test_approve_twice_together_is_one_decision(postgres_engine: AsyncEngine, ctx) -> None:
    approval_id = await _pending(postgres_engine, ctx)

    outcomes = await _decide_together(postgres_engine, ctx, approval_id, ["approved", "approved"])

    assert outcomes == ["approved", "approved"]
    assert await _stored(postgres_engine, approval_id) == ("approved", ["approval.approved"])


@pytest.mark.asyncio
async def test_a_sweep_and_a_decision_together_leave_one_terminal_state(postgres_engine: AsyncEngine, ctx) -> None:
    run_id = f"run-{uuid4().hex}"
    async with AsyncSession(postgres_engine, expire_on_commit=False) as db:
        db.add(Run(id=run_id, tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, user_id="u_owner",
                   mode="agent", kind="agent", status="canceled"))
        approval = ApprovalRequest(tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, run_id=run_id, title="t")
        db.add(approval)
        await db.commit()
        approval_id = approval.id
    barrier = asyncio.Barrier(2)

    async def sweep():
        async with AsyncSession(postgres_engine, expire_on_commit=False) as db:
            await barrier.wait()
            return await close_approvals_of_ended_runs(db)

    async def decide():
        async with AsyncSession(postgres_engine, expire_on_commit=False) as db:
            await barrier.wait()
            try:
                return (await ObserveService(db, ctx).resolve_approval(approval_id, ApprovalResolve(status="approved"))).status
            except ConflictError as exc:
                return exc

    async with asyncio.timeout(RACE_TIMEOUT_SECONDS):
        swept, decided = await asyncio.gather(sweep(), decide())

    stored, events = await _stored(postgres_engine, approval_id)
    if decided == "approved":
        assert (stored, events) == ("approved", ["approval.approved"])
    else:
        assert isinstance(decided, ConflictError) and swept == 1
        assert (stored, events) == ("canceled", ["approval.canceled"])
    async with AsyncSession(postgres_engine) as db:
        await db.exec(delete(Run).where(Run.id == run_id))
        await db.commit()
