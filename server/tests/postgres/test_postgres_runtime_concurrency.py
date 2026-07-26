"""PostgreSQL-only concurrency contracts for durable runtime primitives."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.responses import (
    Response,
    ResponseEvent,
    ResponseInteraction,
)
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.knowledge.domain.models import KnowledgeIngestTask
from app.modules.knowledge.runtime.ingest_worker import GlobalKnowledgeIngestWorker
from app.wiring.response_interaction_worker import GlobalResponseInteractionWorker


@pytest.fixture(scope="module")
def postgres_engine() -> Engine:
    """Use only the explicitly configured PostgreSQL acceptance database."""

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        pytest.skip("DATABASE_URL does not point to PostgreSQL")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )
    engine = create_engine(database_url, pool_pre_ping=True, pool_size=8)
    if engine.dialect.name != "postgresql":
        engine.dispose()
        pytest.skip("PostgreSQL dialect is required")
    yield engine
    engine.dispose()


@pytest.fixture
def scope_token(postgres_engine: Engine):
    """Return a unique scope and remove its rows after each contract."""

    token = uuid4().hex
    tenant_id = f"pg-tenant-{token}"
    workspace_id = f"pg-workspace-{token}"
    yield token, tenant_id, workspace_id
    with Session(postgres_engine) as db:
        db.exec(
            delete(ResponseEvent).where(ResponseEvent.tenant_id == tenant_id)
        )
        db.exec(
            delete(ResponseInteraction).where(
                ResponseInteraction.tenant_id == tenant_id
            )
        )
        db.exec(delete(Response).where(Response.tenant_id == tenant_id))
        db.exec(
            delete(KnowledgeIngestTask).where(
                KnowledgeIngestTask.tenant_id == tenant_id
            )
        )
        db.exec(delete(EventOutbox).where(EventOutbox.tenant_id == tenant_id))
        db.commit()


def test_outbox_lease_has_one_concurrent_winner_and_can_be_reclaimed(
    postgres_engine: Engine,
    scope_token,
) -> None:
    """An outbox row has one owner until its PostgreSQL lease expires."""

    token, tenant_id, workspace_id = scope_token
    row_id = f"outbox-{token}"
    now = utc_now()
    with Session(postgres_engine) as db:
        db.add(
            EventOutbox(
                id=row_id,
                event_id=f"event-{token}",
                event_type="postgres.contract",
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                idempotency_key=f"idem-{token}",
                payload_json={"nested": {"enabled": True}, "items": [1, None, "中"]},
                available_at=now,
                occurred_at=now,
                created_at=now,
            )
        )
        db.commit()

    barrier = Barrier(2)

    def try_claim(owner: str) -> bool:
        with Session(postgres_engine) as db:
            barrier.wait()
            claimed = OutboxRepository(db).try_claim(
                row_id,
                owner=owner,
                now=now,
                lease_seconds=30,
            )
            db.commit()
            return claimed

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(try_claim, ("worker-a", "worker-b")))

    assert sorted(results) == [False, True]
    with Session(postgres_engine) as db:
        row = db.get(EventOutbox, row_id)
        assert row is not None
        assert row.status == "processing"
        assert row.lock_owner in {"worker-a", "worker-b"}
        assert row.payload_json == {
            "nested": {"enabled": True},
            "items": [1, None, "中"],
        }
        selected = db.exec(
            select(EventOutbox).where(
                EventOutbox.payload_json["nested"]["enabled"].as_boolean()
                .is_(True)
            )
        ).scalars().all()
        assert row_id in {item.id for item in selected}
        row.lock_expires_at = now - timedelta(seconds=1)
        db.add(row)
        db.commit()

    with Session(postgres_engine) as db:
        assert OutboxRepository(db).try_claim(
            row_id,
            owner="worker-recovery",
            now=now,
            lease_seconds=30,
        )
        db.commit()
        recovered = db.get(EventOutbox, row_id)
        assert recovered is not None
        assert recovered.lock_owner == "worker-recovery"


def test_response_workers_claim_distinct_rows_with_skip_locked(
    postgres_engine: Engine,
    scope_token,
) -> None:
    """Concurrent response workers never execute the same queued interaction."""

    token, tenant_id, workspace_id = scope_token
    created_at = datetime(2000, 1, 1, tzinfo=UTC)
    interaction_ids = {f"interaction-{token}-a", f"interaction-{token}-b"}
    with Session(postgres_engine) as db:
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
        db.commit()

    barrier = Barrier(2)

    def claim(worker_id: str) -> tuple[str, str, int]:
        worker = GlobalResponseInteractionWorker(
            worker_id=worker_id,
            lease_seconds=30,
        )
        with Session(postgres_engine) as db:
            barrier.wait()
            claimed = worker._claim_next(db)
            assert claimed is not None
            return claimed.interaction_id, str(claimed.lease_owner), claimed.attempt_count

    with ThreadPoolExecutor(max_workers=2) as executor:
        claimed = list(executor.map(claim, ("response-a", "response-b")))

    assert {item[0] for item in claimed} == interaction_ids
    assert {item[1] for item in claimed} == {"response-a", "response-b"}
    assert {item[2] for item in claimed} == {1}


def test_knowledge_workers_claim_distinct_rows_with_skip_locked(
    postgres_engine: Engine,
    scope_token,
) -> None:
    """Concurrent knowledge workers claim separate PostgreSQL tasks."""

    token, tenant_id, workspace_id = scope_token
    created_at = datetime(2000, 1, 1, tzinfo=UTC)
    task_ids = {f"ingest-{token}-a", f"ingest-{token}-b"}
    with Session(postgres_engine) as db:
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
        db.commit()

    barrier = Barrier(2)

    def claim(_: int) -> tuple[str, str]:
        worker = GlobalKnowledgeIngestWorker()
        with Session(postgres_engine) as db:
            barrier.wait()
            claimed = worker._claim_next_task(db)
            assert claimed is not None
            return claimed.id, claimed.status

    with ThreadPoolExecutor(max_workers=2) as executor:
        claimed = list(executor.map(claim, (1, 2)))

    assert {item[0] for item in claimed} == task_ids
    assert {item[1] for item in claimed} == {"running"}


def test_concurrent_response_idempotency_returns_one_owner(
    postgres_engine: Engine,
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
    barrier = Barrier(2)

    def claim(_: int) -> tuple[str, bool]:
        with Session(postgres_engine) as db:
            service = ResponseService(
                db=db,
                ctx=ctx,
                response_repo=ResponseRepository(db, ctx),
                event_repo=ResponseEventRepository(db, ctx),
                trace_writer=TraceWriter(db, ctx),
            )
            barrier.wait()
            interaction, owns_claim = service.claim_interaction(
                interaction_id=interaction_id,
                parent_interaction_id=None,
                thread_id=f"thread-{token}",
                request_hash=f"request-{token}",
                execution_json={"messages": [{"role": "user", "content": "hello"}]},
                request_context_json={"tenant_id": tenant_id},
            )
            return interaction.id, owns_claim

    with ThreadPoolExecutor(max_workers=2) as executor:
        claimed = list(executor.map(claim, (1, 2)))

    assert len({item[0] for item in claimed}) == 1
    assert sorted(item[1] for item in claimed) == [False, True]
    with Session(postgres_engine) as db:
        rows = db.exec(
            select(ResponseInteraction).where(
                ResponseInteraction.tenant_id == tenant_id,
                ResponseInteraction.workspace_id == workspace_id,
                ResponseInteraction.interaction_id == interaction_id,
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].execution_json["messages"][0]["content"] == "hello"


def test_response_event_sequence_is_serialized_on_postgres(
    postgres_engine: Engine,
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
    with Session(postgres_engine) as db:
        db.add(
            Response(
                id=response_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                status="running",
                input_json={"prompt": "sequence"},
            )
        )
        db.commit()

    barrier = Barrier(2)

    def append(index: int) -> int:
        with Session(postgres_engine) as db:
            repo = ResponseEventRepository(db, ctx)
            barrier.wait()
            sequence = repo.next_sequence(response_id)
            repo.create(
                ResponseEvent(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    response_id=response_id,
                    sequence=sequence,
                    type="TEXT_MESSAGE_CONTENT",
                    payload_json={"index": index},
                )
            )
            db.commit()
            return sequence

    with ThreadPoolExecutor(max_workers=2) as executor:
        sequences = list(executor.map(append, (1, 2)))

    assert sorted(sequences) == [1, 2]
