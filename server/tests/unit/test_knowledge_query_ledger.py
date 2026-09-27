"""A knowledge query keeps its run and its usage, whoever called it.

The knowledge_query tool and agent RAG run a query on a session they never
commit, so the query itself commits its run and the cost rows of its model
calls when the run settles.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.runtime.db.models.runs import Run, RunCostEntry
from app.modules.knowledge.application.runtime_schemas import (
    KnowledgeCreate,
    QueryRequest,
)
from app.wiring.services import build_knowledge_runtime_service

pytestmark = pytest.mark.asyncio


class _PricedRetrieval:
    """Retrieval whose embedding call records a priced cost, then answers or waits."""

    def __init__(self, writer: Any, *, wait: bool = False) -> None:
        self.writer = writer
        self.wait = wait
        self.recorded = asyncio.Event()

    async def query(self, *, run_id: str, **kwargs: Any) -> list[Any]:
        del kwargs
        # As a model call does: the running run is committed before the wait.
        await self.writer.release_before_wait()
        await self.writer.record_cost(
            run_id=run_id,
            step_id=None,
            billing_basis="embeddings",
            billed_quantity=1,
            currency="USD",
            amount=Decimal("0.01"),
            source_port="llm",
            operation="embed",
        )
        self.recorded.set()
        if self.wait:
            await asyncio.Event().wait()
        return []


async def _service_on_its_own_session(async_db, ctx):
    session = AsyncSession(async_db.bind, expire_on_commit=False)
    service = build_knowledge_runtime_service(db=session, ctx=ctx)
    knowledge = await service.create_knowledge(KnowledgeCreate(name="ledger-kb", type="document"))
    await session.commit()
    return session, service, knowledge.id


async def _query_runs(async_db) -> tuple[list[Run], list[RunCostEntry]]:
    async_db.expire_all()
    runs = list((await async_db.exec(select(Run).where(Run.mode == "knowledge_query"))).all())
    costs = list((await async_db.exec(select(RunCostEntry))).all())
    return runs, costs


async def test_a_query_nobody_commits_keeps_its_run_and_usage(async_db, ctx) -> None:
    session, service, knowledge_id = await _service_on_its_own_session(async_db, ctx)
    service.retrieval_service = _PricedRetrieval(service.trace_writer)

    await service.query(knowledge_id, QueryRequest(query="refund policy"))
    await session.close()  # as the tool entrypoint does, without committing

    runs, costs = await _query_runs(async_db)
    assert [run.status for run in runs] == ["succeeded"]
    assert [(cost.run_id, cost.amount) for cost in costs] == [(runs[0].id, Decimal("0.01"))]


async def test_a_canceled_query_keeps_its_run_and_usage(async_db, ctx) -> None:
    session, service, knowledge_id = await _service_on_its_own_session(async_db, ctx)
    retrieval = _PricedRetrieval(service.trace_writer, wait=True)
    service.retrieval_service = retrieval

    task = asyncio.create_task(service.query(knowledge_id, QueryRequest(query="refund policy")))
    await retrieval.recorded.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await session.close()

    runs, costs = await _query_runs(async_db)
    assert [run.status for run in runs] == ["canceled"]
    assert [cost.amount for cost in costs] == [Decimal("0.01")]
