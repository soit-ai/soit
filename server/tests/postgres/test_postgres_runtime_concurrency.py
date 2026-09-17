"""PostgreSQL-only concurrency contracts for durable runtime primitives.

Every race here runs its contenders as coroutines on their own
``AsyncSession``, released together by an ``asyncio.Barrier`` so their
transactions really overlap on the server. That is what exercises
``SELECT ... FOR UPDATE SKIP LOCKED`` and the conditional-UPDATE claims;
SQLite cannot hold two write transactions open, so nothing here has a
SQLite twin.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import TypeVar
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.runtime.common import lease
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.responses import (
    Response,
    ResponseEvent,
    ResponseInteraction,
)
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.knowledge.domain.models import KnowledgeIngestTask
from app.modules.knowledge.runtime.ingest_worker import GlobalKnowledgeIngestWorker
from app.modules.workflow.domain.models import WorkflowRun
from app.modules.workflow.runtime.reaper import (
    ORPHANED_ERROR_CODE,
    reap_orphaned_workflow_runs,
)
from app.wiring.response_interaction_worker import GlobalResponseInteractionWorker

if sys.platform == "win32":
    # psycopg's async mode refuses the Proactor loop that pytest-asyncio
    # would otherwise create on Windows.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

T = TypeVar("T")

# Upper bound on one race. A contender that never reaches the barrier would
# otherwise hang the whole module instead of failing the one contract.
RACE_TIMEOUT_SECONDS = 60


@pytest_asyncio.fixture
async def postgres_engine() -> AsyncEngine:
    """Use only the explicitly configured PostgreSQL acceptance database."""

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        pytest.skip("DATABASE_URL does not point to PostgreSQL")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )
    engine = create_async_engine(database_url, pool_pre_ping=True, pool_size=8)
    if engine.dialect.name != "postgresql":
        await engine.dispose()
        pytest.skip("PostgreSQL dialect is required")
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def scope_token(postgres_engine: AsyncEngine):
    """Return a unique scope and remove its rows after each contract."""

    token = uuid4().hex
    tenant_id = f"pg-tenant-{token}"
    workspace_id = f"pg-workspace-{token}"
    yield token, tenant_id, workspace_id
    async with AsyncSession(postgres_engine) as db:
        await db.exec(
            delete(ResponseEvent).where(ResponseEvent.tenant_id == tenant_id)
        )
        await db.exec(
            delete(ResponseInteraction).where(
                ResponseInteraction.tenant_id == tenant_id
            )
        )
        await db.exec(delete(Response).where(Response.tenant_id == tenant_id))
        await db.exec(
            delete(KnowledgeIngestTask).where(
                KnowledgeIngestTask.tenant_id == tenant_id
            )
        )
        await db.exec(delete(WorkflowRun).where(WorkflowRun.tenant_id == tenant_id))
        await db.exec(delete(Run).where(Run.tenant_id == tenant_id))
        await db.exec(delete(EventOutbox).where(EventOutbox.tenant_id == tenant_id))
        await db.commit()


def _session(engine: AsyncEngine) -> AsyncSession:
    return AsyncSession(engine, expire_on_commit=False)


async def _race(
    engine: AsyncEngine,
    contenders: Sequence[Callable[[AsyncSession], Awaitable[T]]],
) -> list[T]:
    """Run each contender on its own session, released together by a barrier.

    The barrier sits inside the session scope so every contender has its
    session ready before any of them touches the database; the first
    statement each one issues then lands while the others are in flight,
    which is the overlap the row-locking contracts depend on.
    """

    barrier = asyncio.Barrier(len(contenders))

    async def run(contender: Callable[[AsyncSession], Awaitable[T]]) -> T:
        async with _session(engine) as db:
            await barrier.wait()
            return await contender(db)

    async with asyncio.timeout(RACE_TIMEOUT_SECONDS):
        return list(await asyncio.gather(*(run(item) for item in contenders)))


@pytest.mark.asyncio
async def test_outbox_lease_has_one_concurrent_winner_and_can_be_reclaimed(
    postgres_engine: AsyncEngine,
    scope_token,
) -> None:
    """An outbox row has one owner until its PostgreSQL lease expires."""

    token, tenant_id, workspace_id = scope_token
    row_id = f"outbox-{token}"
    now = utc_now()
    async with _session(postgres_engine) as db:
        db.add(
            EventOutbox(
                id=row_id,
                event_id=f"event-{token}",
                event_type="postgres.contract",
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                idempotency_key=f"idem-{token}",
                # The non-ASCII item is deliberate: it proves JSONB round-trips
                # multi-byte UTF-8 (2-byte and 3-byte code points).
                payload_json={"nested": {"enabled": True}, "items": [1, None, "ünicode-✓"]},
                available_at=now,
                occurred_at=now,
                created_at=now,
            )
        )
        await db.commit()

    def try_claim(owner: str) -> Callable[[AsyncSession], Awaitable[bool]]:
        async def contender(db: AsyncSession) -> bool:
            claimed = await OutboxRepository(db).try_claim(
                row_id,
                owner=owner,
                now=now,
                lease_seconds=30,
            )
            await db.commit()
            return claimed

        return contender

    results = await _race(postgres_engine, [try_claim("worker-a"), try_claim("worker-b")])

    assert sorted(results) == [False, True]
    async with _session(postgres_engine) as db:
        row = await db.get(EventOutbox, row_id)
        assert row is not None
        assert row.status == "processing"
        assert row.lock_owner in {"worker-a", "worker-b"}
        assert row.payload_json == {
            "nested": {"enabled": True},
            "items": [1, None, "ünicode-✓"],
        }
        selected = (
            await db.exec(
                select(EventOutbox).where(
                    EventOutbox.payload_json["nested"]["enabled"].as_boolean()
                    .is_(True)
                )
            )
        ).scalars().all()
        assert row_id in {item.id for item in selected}
        row.lock_expires_at = now - timedelta(seconds=1)
        db.add(row)
        await db.commit()

    async with _session(postgres_engine) as db:
        assert await OutboxRepository(db).try_claim(
            row_id,
            owner="worker-recovery",
            now=now,
            lease_seconds=30,
        )
        await db.commit()
        recovered = await db.get(EventOutbox, row_id)
        assert recovered is not None
        assert recovered.lock_owner == "worker-recovery"


@pytest.mark.asyncio
async def test_response_workers_claim_distinct_rows_with_skip_locked(
    postgres_engine: AsyncEngine,
    scope_token,
) -> None:
    """Concurrent response workers never execute the same queued interaction."""

    token, tenant_id, workspace_id = scope_token
    created_at = datetime(2000, 1, 1, tzinfo=UTC)
    interaction_ids = {f"interaction-{token}-a", f"interaction-{token}-b"}
    async with _session(postgres_engine) as db:
        for index, interaction_id in enumerate(sorted(interaction_ids)):
            db.add(
                ResponseInteraction(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    interaction_id=interaction_id,
                    thread_id=f"thread-{token}",
                    request_hash=f"hash-{index}",
                    status="queued",
                    created_by="pg-user",
                    created_at=created_at + timedelta(microseconds=index),
                    updated_at=created_at + timedelta(microseconds=index),
                )
            )
        await db.commit()

    def claim(worker_id: str) -> Callable[[AsyncSession], Awaitable[tuple[str, str, int]]]:
        async def contender(db: AsyncSession) -> tuple[str, str, int]:
            worker = GlobalResponseInteractionWorker(
                worker_id=worker_id,
                lease_seconds=30,
            )
            claimed = await worker._claim_next(db)
            assert claimed is not None
            return claimed.interaction_id, str(claimed.lease_owner), claimed.attempt_count

        return contender

    claimed = await _race(postgres_engine, [claim("response-a"), claim("response-b")])

    assert {item[0] for item in claimed} == interaction_ids
    assert {item[1] for item in claimed} == {"response-a", "response-b"}
    assert {item[2] for item in claimed} == {1}


@pytest.mark.asyncio
async def test_knowledge_workers_claim_distinct_rows_with_skip_locked(
    postgres_engine: AsyncEngine,
    scope_token,
) -> None:
    """Concurrent knowledge workers claim separate PostgreSQL tasks."""

    token, tenant_id, workspace_id = scope_token
    created_at = datetime(2000, 1, 1, tzinfo=UTC)
    task_ids = {f"ingest-{token}-a", f"ingest-{token}-b"}
    async with _session(postgres_engine) as db:
        for index, task_id in enumerate(sorted(task_ids)):
            db.add(
                KnowledgeIngestTask(
                    id=task_id,
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    knowledge_id=f"knowledge-{token}",
                    status="queued",
                    payload_json={"ordinal": index},
                    created_by="pg-user",
                    created_at=created_at + timedelta(microseconds=index),
                    updated_at=created_at + timedelta(microseconds=index),
                )
            )
        await db.commit()

    async def claim(db: AsyncSession) -> tuple[str, str]:
        worker = GlobalKnowledgeIngestWorker()
        claimed = await worker._claim_next_task(db)
        assert claimed is not None
        return claimed.id, claimed.status

    claimed = await _race(postgres_engine, [claim, claim])

    assert {item[0] for item in claimed} == task_ids
    assert {item[1] for item in claimed} == {"running"}


@pytest.mark.asyncio
async def test_knowledge_lease_is_exclusive_until_it_expires_on_postgres(
    postgres_engine: AsyncEngine,
    scope_token,
) -> None:
    """A held knowledge lease blocks other workers; an expired one is reclaimed."""

    token, tenant_id, workspace_id = scope_token
    task_id = f"ingest-lease-{token}"
    created_at = datetime(2000, 1, 1, tzinfo=UTC)
    async with _session(postgres_engine) as db:
        db.add(
            KnowledgeIngestTask(
                id=task_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                knowledge_id=f"knowledge-{token}",
                status="queued",
                created_by="pg-user",
                created_at=created_at,
                updated_at=created_at,
            )
        )
        await db.commit()

    holder = GlobalKnowledgeIngestWorker(worker_id="pg-worker-holder", lease_seconds=600)
    rescuer = GlobalKnowledgeIngestWorker(worker_id="pg-worker-rescue", lease_seconds=600)

    async with _session(postgres_engine) as db:
        claimed = await holder._claim_next_task(db)
        assert claimed is not None
        assert claimed.id == task_id
        assert claimed.lease_owner == "pg-worker-holder"
        assert claimed.attempt_count == 1

    async with _session(postgres_engine) as db:
        assert await rescuer._claim_next_task(db) is None

    async with _session(postgres_engine) as db:
        renewal = await lease.renew_lease(
            db,
            KnowledgeIngestTask,
            task_id,
            worker_id="pg-worker-holder",
            attempt_count=1,
            lease_seconds=600,
        )
        assert renewal is lease.LeaseRenewal.RENEWED

    # Simulate the holder dying: it stops renewing and the lease lapses.
    async with _session(postgres_engine) as db:
        stranded = await db.get(KnowledgeIngestTask, task_id)
        assert stranded is not None
        stranded.lease_expires_at = utc_now() - timedelta(minutes=5)
        db.add(stranded)
        await db.commit()

    async with _session(postgres_engine) as db:
        recovered = await rescuer._claim_next_task(db)
        assert recovered is not None
        assert recovered.id == task_id
        assert recovered.lease_owner == "pg-worker-rescue"
        assert recovered.attempt_count == 2

    async with _session(postgres_engine) as db:
        assert (
            await lease.renew_lease(
                db,
                KnowledgeIngestTask,
                task_id,
                worker_id="pg-worker-holder",
                attempt_count=1,
                lease_seconds=600,
            )
            is lease.LeaseRenewal.LOST
        )


@pytest.mark.asyncio
async def test_expired_knowledge_lease_has_one_concurrent_rescuer_on_postgres(
    postgres_engine: AsyncEngine,
    scope_token,
) -> None:
    """Only one of several racing workers reclaims an expired knowledge lease."""

    token, tenant_id, workspace_id = scope_token
    task_id = f"ingest-orphan-{token}"
    created_at = datetime(2000, 1, 1, tzinfo=UTC)
    async with _session(postgres_engine) as db:
        db.add(
            KnowledgeIngestTask(
                id=task_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                knowledge_id=f"knowledge-{token}",
                status="running",
                lease_owner="pg-worker-dead",
                lease_expires_at=utc_now() - timedelta(minutes=5),
                attempt_count=1,
                created_by="pg-user",
                created_at=created_at,
                updated_at=created_at,
            )
        )
        await db.commit()

    def reclaim(index: int) -> Callable[[AsyncSession], Awaitable[str | None]]:
        async def contender(db: AsyncSession) -> str | None:
            worker = GlobalKnowledgeIngestWorker(
                worker_id=f"pg-worker-rescue-{index}",
                lease_seconds=600,
            )
            claimed = await worker._claim_next_task(db)
            return None if claimed is None else claimed.lease_owner

        return contender

    owners = await _race(postgres_engine, [reclaim(1), reclaim(2), reclaim(3)])

    winners = [owner for owner in owners if owner is not None]
    assert len(winners) == 1
    async with _session(postgres_engine) as db:
        row = await db.get(KnowledgeIngestTask, task_id)
        assert row is not None
        assert row.lease_owner == winners[0]
        assert row.attempt_count == 2


@pytest.mark.asyncio
async def test_orphaned_workflow_run_is_reaped_once_under_concurrency(
    postgres_engine: AsyncEngine,
    scope_token,
) -> None:
    """Concurrent sweeps fail an abandoned workflow run exactly once."""

    token, tenant_id, workspace_id = scope_token
    run_id = f"run-wf-orphan-{token}"
    async with _session(postgres_engine) as db:
        db.add(
            Run(
                id=run_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                user_id="pg-user",
                trace_id=f"tr-{token}",
                mode="workflow",
                kind="workflow",
                status="running",
            )
        )
        db.add(
            WorkflowRun(
                id=f"wfr-orphan-{token}",
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                run_id=run_id,
                workflow_id=f"wf-{token}",
                status="running",
                lease_owner="workflow-api-dead",
                lease_expires_at=utc_now() - timedelta(minutes=5),
                attempt_count=1,
            )
        )
        await db.commit()

    async def sweep(db: AsyncSession) -> int:
        try:
            return await reap_orphaned_workflow_runs(db)
        except Exception:
            # A loser may hit a write conflict; the contract is that the
            # row ends up failed exactly once, not that every sweep wins.
            await db.rollback()
            return 0

    reaped = await _race(postgres_engine, [sweep, sweep, sweep])

    assert sum(reaped) == 1
    async with _session(postgres_engine) as db:
        row = await db.get(WorkflowRun, f"wfr-orphan-{token}")
        run = await db.get(Run, run_id)
        assert row is not None and run is not None
        assert row.status == "failed"
        assert row.lease_owner is None
        assert row.lease_expires_at is None
        assert run.status == "failed"
        assert run.error_code == ORPHANED_ERROR_CODE


@pytest.mark.asyncio
async def test_concurrent_redrive_staging_claims_a_dead_run_once(
    postgres_engine: AsyncEngine,
    scope_token,
) -> None:
    """Two operators redriving the same dead run produce one resumed attempt.

    Staging is a conditional UPDATE on the failed status. SQLite cannot prove
    this: without real row locking both writers would appear to succeed and
    the run would be executed twice, repeating every side effect after the
    checkpoint.
    """

    token, tenant_id, workspace_id = scope_token
    run_id = f"run-wf-redrive-{token}"
    row_id = f"wfr-redrive-{token}"
    async with _session(postgres_engine) as db:
        db.add(
            Run(
                id=run_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                user_id="pg-user",
                trace_id=f"tr-{token}",
                mode="workflow",
                kind="workflow",
                status="failed",
            )
        )
        db.add(
            WorkflowRun(
                id=row_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                run_id=run_id,
                workflow_id=f"wf-{token}",
                status="failed",
                completed_nodes=1,
                total_nodes=3,
                checkpoint_json={
                    "inputs": {},
                    "node_states": {"a": "succeeded"},
                    "node_outputs": {"a": {"x": 1}},
                    "truncated_node_ids": [],
                },
            )
        )
        await db.commit()

    def stage(worker: int) -> Callable[[AsyncSession], Awaitable[int]]:
        """Run the same compare-and-set the redrive path uses."""

        async def contender(db: AsyncSession) -> int:
            try:
                result = await db.exec(
                    update(WorkflowRun)
                    .where(
                        WorkflowRun.id == row_id,
                        WorkflowRun.status == "failed",
                    )
                    .values(
                        status="queued",
                        lease_owner=f"workflow-redrive-{worker}",
                        lease_expires_at=utc_now() + timedelta(minutes=2),
                        attempt_count=WorkflowRun.attempt_count + 1,
                        updated_at=utc_now(),
                    )
                )
                await db.commit()
                return int(result.rowcount or 0)
            except Exception:
                await db.rollback()
                return 0

        return contender

    staged = await _race(postgres_engine, [stage(1), stage(2), stage(3)])

    assert sum(staged) == 1
    async with _session(postgres_engine) as db:
        row = await db.get(WorkflowRun, row_id)
        assert row is not None
        assert row.status == "queued"
        # Exactly one increment: a second claim would mean a second execution.
        assert row.attempt_count == 1
        assert row.lease_owner is not None
        # The checkpoint must survive staging, or the resume restarts from zero.
        assert (row.checkpoint_json or {})["node_states"] == {"a": "succeeded"}


@pytest.mark.asyncio
async def test_live_workflow_lease_survives_a_sweep_on_postgres(
    postgres_engine: AsyncEngine,
    scope_token,
) -> None:
    """A workflow still renewing its lease is never reaped."""

    token, tenant_id, workspace_id = scope_token
    run_id = f"run-wf-live-{token}"
    async with _session(postgres_engine) as db:
        db.add(
            WorkflowRun(
                id=f"wfr-live-{token}",
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                run_id=run_id,
                workflow_id=f"wf-{token}",
                status="running",
                lease_owner="workflow-api-alive",
                lease_expires_at=utc_now() + timedelta(minutes=10),
                attempt_count=1,
            )
        )
        await db.commit()

    async with _session(postgres_engine) as db:
        assert await reap_orphaned_workflow_runs(db) == 0
        row = await db.get(WorkflowRun, f"wfr-live-{token}")
        assert row is not None
        assert row.status == "running"
        assert row.lease_owner == "workflow-api-alive"


@pytest.mark.asyncio
async def test_concurrent_response_idempotency_returns_one_owner(
    postgres_engine: AsyncEngine,
    scope_token,
) -> None:
    """The unique interaction contract resolves concurrent inserts to one owner."""

    token, tenant_id, workspace_id = scope_token
    interaction_id = f"idempotent-{token}"
    ctx = RequestContext(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_id="pg-user",
        tenant_role="Owner",
        workspace_role="Owner",
    )

    async def claim(db: AsyncSession) -> tuple[str, bool]:
        service = ResponseService(
            db=db,
            ctx=ctx,
            response_repo=ResponseRepository(db, ctx),
            event_repo=ResponseEventRepository(db, ctx),
            trace_writer=TraceWriter(db, ctx),
        )
        interaction, owns_claim = await service.claim_interaction(
            interaction_id=interaction_id,
            parent_interaction_id=None,
            thread_id=f"thread-{token}",
            request_hash=f"request-{token}",
            execution_json={"messages": [{"role": "user", "content": "hello"}]},
            request_context_json={"tenant_id": tenant_id},
        )
        return interaction.id, owns_claim

    claimed = await _race(postgres_engine, [claim, claim])

    assert len({item[0] for item in claimed}) == 1
    assert sorted(item[1] for item in claimed) == [False, True]
    async with _session(postgres_engine) as db:
        rows = (
            await db.exec(
                select(ResponseInteraction).where(
                    ResponseInteraction.tenant_id == tenant_id,
                    ResponseInteraction.workspace_id == workspace_id,
                    ResponseInteraction.interaction_id == interaction_id,
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].execution_json["messages"][0]["content"] == "hello"


@pytest.mark.asyncio
async def test_response_event_sequence_is_serialized_on_postgres(
    postgres_engine: AsyncEngine,
    scope_token,
) -> None:
    """Concurrent writers allocate distinct response event sequences."""

    token, tenant_id, workspace_id = scope_token
    response_id = f"response-{token}"
    ctx = RequestContext(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_id="pg-user",
        tenant_role="Owner",
        workspace_role="Owner",
    )
    async with _session(postgres_engine) as db:
        db.add(
            Response(
                id=response_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                status="running",
                input_json={"prompt": "sequence"},
            )
        )
        await db.commit()

    def append(index: int) -> Callable[[AsyncSession], Awaitable[int]]:
        async def contender(db: AsyncSession) -> int:
            repo = ResponseEventRepository(db, ctx)
            sequence = await repo.next_sequence(response_id)
            await repo.create(
                ResponseEvent(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    response_id=response_id,
                    sequence=sequence,
                    type="TEXT_MESSAGE_CONTENT",
                    payload_json={"index": index},
                )
            )
            await db.commit()
            return sequence

        return contender

    sequences = await _race(postgres_engine, [append(1), append(2)])

    assert sorted(sequences) == [1, 2]
