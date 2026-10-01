"""Knowledge sync worker: claiming, lease recovery, scheduling, dead letters."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.runtime.deadletter.contracts import (
    DeadLetterKind,
    RedriveOutcome,
    clear_dead_letter_sources,
)
from app.kernel.runtime.deadletter.service import DeadLetterService
from app.modules.knowledge.application.connector_sync import (
    compute_next_sync,
    create_sync_run,
    enqueue_due_runs,
)
from app.modules.knowledge.application.runtime_schemas import KnowledgeCreate
from app.modules.knowledge.domain.models import (
    KnowledgeDocument,
    KnowledgeSource,
    KnowledgeSyncRun,
)
from app.modules.knowledge.runtime.sync_worker import GlobalKnowledgeSyncWorker
from app.settings.settings import settings
from app.wiring.dead_letter_sources import register_dead_letter_sources
from tests.unit.knowledge_connector_support import FakeRemote, build_registry
from tests.unit.test_knowledge_runtime_service import build_knowledge_test_service


@pytest.fixture(autouse=True)
def dead_letter_sources():
    clear_dead_letter_sources()
    register_dead_letter_sources()
    yield
    clear_dead_letter_sources()


def session_factory(async_db):
    return lambda: AsyncSession(async_db.bind, expire_on_commit=False)


async def _setup(async_db, ctx, **source_kwargs):
    service, _storage, _vector = build_knowledge_test_service(async_db, ctx)
    knowledge = await service.create_knowledge(
        KnowledgeCreate(name="kb_worker", type="document", default_embedding_model_ref="model:test:embedding")
    )
    source = KnowledgeSource(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        knowledge_id=knowledge.id,
        name="bucket docs",
        connector_kind="fake",
        config_json={"bucket": "docs"},
        created_by=ctx.user_id,
        **source_kwargs,
    )
    async_db.add(source)
    await async_db.commit()
    remote = FakeRemote()
    worker = GlobalKnowledgeSyncWorker(
        session_factory(async_db),
        worker_id="worker-1",
        registry=build_registry(remote),
        scheduler_interval_seconds=1,
    )
    return knowledge, source, remote, worker


async def _fresh(async_db, model, key):
    statement = select(model).where(model.id == key).execution_options(populate_existing=True)
    return (await async_db.exec(statement)).scalars().one()


@pytest.mark.asyncio
async def test_worker_claims_a_queued_run_and_syncs_the_source(async_db, ctx) -> None:
    knowledge, source, remote, worker = await _setup(async_db, ctx)
    remote.put("a.txt", b"one")
    run = await create_sync_run(async_db, source, trigger="manual", requested_by="alice")

    processed = await worker.run_once()

    assert processed is not None and processed.id == run.id
    finished = await _fresh(async_db, KnowledgeSyncRun, run.id)
    assert finished.status == "succeeded" and finished.added_count == 1
    assert finished.attempt_count == 1 and finished.lease_owner is None
    documents = (await async_db.exec(select(KnowledgeDocument))).scalars().all()
    assert [(doc.external_id, doc.created_by) for doc in documents] == [("a.txt", "alice")]
    refreshed = await _fresh(async_db, KnowledgeSource, source.id)
    assert refreshed.last_status == "succeeded"


@pytest.mark.asyncio
async def test_worker_returns_nothing_when_no_run_is_queued(async_db, ctx) -> None:
    _knowledge, _source, _remote, worker = await _setup(async_db, ctx)

    assert await worker.run_once() is None


@pytest.mark.asyncio
async def test_scheduled_runs_execute_as_the_system_user(async_db, ctx) -> None:
    knowledge, source, remote, worker = await _setup(async_db, ctx)
    remote.put("a.txt", b"one")
    await create_sync_run(async_db, source, trigger="schedule", requested_by=None)

    await worker.run_once()

    documents = (await async_db.exec(select(KnowledgeDocument))).scalars().all()
    assert [doc.created_by for doc in documents] == ["system"]


@pytest.mark.asyncio
async def test_a_run_orphaned_by_a_dead_worker_is_reclaimed_and_finished(async_db, ctx) -> None:
    knowledge, source, remote, worker = await _setup(async_db, ctx)
    remote.put("a.txt", b"one")
    run = await create_sync_run(async_db, source, trigger="manual", requested_by="alice")
    run.status = "running"
    run.lease_owner = "dead-worker"
    run.lease_expires_at = utc_now() - timedelta(minutes=5)
    run.attempt_count = 1
    await async_db.commit()

    processed = await worker.run_once()

    assert processed is not None
    finished = await _fresh(async_db, KnowledgeSyncRun, run.id)
    assert finished.status == "succeeded" and finished.attempt_count == 2


@pytest.mark.asyncio
async def test_a_run_with_a_live_lease_is_left_alone(async_db, ctx) -> None:
    knowledge, source, remote, worker = await _setup(async_db, ctx)
    run = await create_sync_run(async_db, source, trigger="manual", requested_by="alice")
    run.status = "running"
    run.lease_owner = "other-worker"
    run.lease_expires_at = utc_now() + timedelta(minutes=5)
    await async_db.commit()

    assert await worker.run_once() is None
    assert (await _fresh(async_db, KnowledgeSyncRun, run.id)).lease_owner == "other-worker"


@pytest.mark.asyncio
async def test_a_run_interrupted_too_many_times_is_given_up(async_db, ctx, monkeypatch) -> None:
    monkeypatch.setattr(settings, "knowledge_sync_max_attempts", 2)
    knowledge, source, remote, worker = await _setup(async_db, ctx)
    remote.put("a.txt", b"one")
    run = await create_sync_run(async_db, source, trigger="manual", requested_by="alice")
    run.status = "running"
    run.lease_owner = "dead-worker"
    run.lease_expires_at = utc_now() - timedelta(minutes=5)
    run.attempt_count = 2
    await async_db.commit()

    await worker.run_once()

    finished = await _fresh(async_db, KnowledgeSyncRun, run.id)
    assert finished.status == "failed" and finished.error_code == "SYNC_ATTEMPTS_EXHAUSTED"
    assert remote.fetches == []
    assert (await _fresh(async_db, KnowledgeSource, source.id)).last_status == "failed"


@pytest.mark.asyncio
async def test_an_unexpected_crash_is_recorded_on_the_run(async_db, ctx, monkeypatch) -> None:
    from app.modules.knowledge.application import connector_sync

    knowledge, source, remote, worker = await _setup(async_db, ctx)
    run = await create_sync_run(async_db, source, trigger="manual", requested_by="alice")

    async def explode(*_args, **_kwargs):
        raise RuntimeError("worker blew up")

    monkeypatch.setattr(connector_sync.KnowledgeSyncEngine, "execute", explode)

    await worker.run_once()

    finished = await _fresh(async_db, KnowledgeSyncRun, run.id)
    assert finished.status == "failed" and "worker blew up" in finished.error_message
    assert finished.lease_owner is None
    assert (await _fresh(async_db, KnowledgeSource, source.id)).last_error == finished.error_message


@pytest.mark.asyncio
async def test_a_worker_whose_lease_was_taken_does_not_overwrite_the_new_owner(async_db, ctx, monkeypatch) -> None:
    from app.modules.knowledge.application import connector_sync

    knowledge, source, remote, worker = await _setup(async_db, ctx)
    remote.put("a.txt", b"one")
    run = await create_sync_run(async_db, source, trigger="manual", requested_by="alice")
    real_execute = connector_sync.KnowledgeSyncEngine.execute

    async def steal_then_run(self, run, *, lease_owner=None):
        thief = session_factory(async_db)()
        row = await thief.get(KnowledgeSyncRun, run.id)
        row.lease_owner = "thief"
        await thief.commit()
        await thief.close()
        return await real_execute(self, run, lease_owner=lease_owner)

    monkeypatch.setattr(connector_sync.KnowledgeSyncEngine, "execute", steal_then_run)

    await worker.run_once()

    row = await _fresh(async_db, KnowledgeSyncRun, run.id)
    assert row.lease_owner == "thief" and row.status == "running"


# --------------------------------------------------------------- scheduling


def test_next_sync_follows_the_cron_expression_in_its_time_zone() -> None:
    source = KnowledgeSource(
        tenant_id="t", workspace_id="w", knowledge_id="k", name="n", connector_kind="fake",
        schedule_cron="*/15 * * * *", schedule_timezone="UTC",
    )
    assert compute_next_sync(source, after=datetime(2026, 10, 1, 10, 7, tzinfo=UTC)) == datetime(2026, 10, 1, 10, 15, tzinfo=UTC)

    source.schedule_cron = "0 2 * * *"
    source.schedule_timezone = "Asia/Shanghai"
    assert compute_next_sync(source, after=datetime(2026, 10, 1, 10, 7, tzinfo=UTC)) == datetime(2026, 10, 1, 18, 0, tzinfo=UTC)


def test_next_sync_is_none_without_a_schedule_or_when_disabled_or_broken() -> None:
    source = KnowledgeSource(tenant_id="t", workspace_id="w", knowledge_id="k", name="n", connector_kind="fake")
    now = utc_now()
    assert compute_next_sync(source, after=now) is None
    source.schedule_cron = "0 * * * *"
    source.enabled = False
    assert compute_next_sync(source, after=now) is None
    source.enabled = True
    source.schedule_cron = "not a cron"
    assert compute_next_sync(source, after=now) is None


@pytest.mark.asyncio
async def test_due_sources_are_queued_once_per_scheduler_interval_and_then_executed(async_db, ctx) -> None:
    knowledge, source, remote, worker = await _setup(
        async_db, ctx, schedule_cron="0 * * * *", next_sync_at=utc_now() - timedelta(minutes=1)
    )
    remote.put("a.txt", b"one")

    assert await worker.enqueue_due() == 1
    assert await worker.enqueue_due() == 0  # inside the scheduler interval

    processed = await worker.run_loop(poll_interval=0.01, max_runs=1)

    assert processed == 1
    runs = (await async_db.exec(select(KnowledgeSyncRun))).scalars().all()
    assert [(run.trigger, run.status, run.added_count) for run in runs] == [("schedule", "succeeded", 1)]
    refreshed = await _fresh(async_db, KnowledgeSource, source.id)
    assert refreshed.last_status == "succeeded"
    next_sync = refreshed.next_sync_at.replace(tzinfo=None) if refreshed.next_sync_at.tzinfo else refreshed.next_sync_at
    assert next_sync > datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)


@pytest.mark.asyncio
async def test_a_source_that_is_still_syncing_is_not_queued_again_when_due(async_db, ctx) -> None:
    knowledge, source, remote, worker = await _setup(
        async_db, ctx, schedule_cron="* * * * *", next_sync_at=utc_now() - timedelta(minutes=1)
    )
    await create_sync_run(async_db, source, trigger="manual", requested_by="alice")

    assert await enqueue_due_runs(async_db) == 0
    assert len((await async_db.exec(select(KnowledgeSyncRun))).scalars().all()) == 1


# ------------------------------------------------------------- dead letters


@pytest.mark.asyncio
async def test_failed_runs_show_as_dead_letters_until_a_later_run_supersedes_them(async_db, ctx) -> None:
    knowledge, source, remote, worker = await _setup(async_db, ctx)
    failed = await create_sync_run(async_db, source, trigger="manual", requested_by="alice")
    failed.status = "failed"
    failed.error_code = "CONNECTOR_AUTH_FAILED"
    failed.error_message = "The credentials were rejected"
    failed.finished_at = utc_now()
    await async_db.commit()
    service = DeadLetterService(async_db, ctx)

    letters = await service.list_dead_letters(kind=DeadLetterKind.KNOWLEDGE_SYNC)

    assert [(item.id, item.subject, item.error_code, item.redrivable) for item in letters] == [
        (failed.id, "bucket docs", "CONNECTOR_AUTH_FAILED", True)
    ]
    assert letters[0].details["source_id"] == source.id

    later = await create_sync_run(async_db, source, trigger="manual", requested_by="alice")
    later.status = "succeeded"
    later.created_at = failed.created_at + timedelta(seconds=5)
    await async_db.commit()

    assert await service.list_dead_letters(kind=DeadLetterKind.KNOWLEDGE_SYNC) == []


@pytest.mark.asyncio
async def test_partial_runs_are_not_dead_letters(async_db, ctx) -> None:
    knowledge, source, remote, worker = await _setup(async_db, ctx)
    run = await create_sync_run(async_db, source, trigger="manual", requested_by="alice")
    run.status = "partial"
    await async_db.commit()

    assert await DeadLetterService(async_db, ctx).list_dead_letters(kind=DeadLetterKind.KNOWLEDGE_SYNC) == []


@pytest.mark.asyncio
async def test_redriving_a_failed_sync_queues_a_new_run_that_the_worker_executes(async_db, ctx) -> None:
    knowledge, source, remote, worker = await _setup(async_db, ctx)
    remote.put("a.txt", b"one")
    failed = await create_sync_run(async_db, source, trigger="manual", requested_by="alice")
    failed.status = "failed"
    failed.finished_at = utc_now()
    await async_db.commit()

    result = await DeadLetterService(async_db, ctx).redrive(
        kind=DeadLetterKind.KNOWLEDGE_SYNC, dead_letter_id=failed.id
    )

    assert result.outcome is RedriveOutcome.REDRIVEN and result.redriven_as
    queued = await _fresh(async_db, KnowledgeSyncRun, result.redriven_as)
    assert queued.status == "queued" and queued.source_id == source.id and queued.requested_by == ctx.user_id
    assert (await _fresh(async_db, KnowledgeSyncRun, failed.id)).status == "failed"
    assert await DeadLetterService(async_db, ctx).list_dead_letters(kind=DeadLetterKind.KNOWLEDGE_SYNC) == []

    await worker.run_once()
    assert (await _fresh(async_db, KnowledgeSyncRun, queued.id)).status == "succeeded"


@pytest.mark.asyncio
async def test_redrive_is_refused_while_another_sync_is_active_or_the_source_is_gone(async_db, ctx) -> None:
    knowledge, source, remote, worker = await _setup(async_db, ctx)
    failed = await create_sync_run(async_db, source, trigger="manual", requested_by="alice")
    failed.status = "failed"
    failed.finished_at = utc_now()
    await async_db.commit()
    await create_sync_run(async_db, source, trigger="manual", requested_by="alice")
    service = DeadLetterService(async_db, ctx)

    busy = await service.redrive(kind=DeadLetterKind.KNOWLEDGE_SYNC, dead_letter_id=failed.id)
    assert busy.outcome is RedriveOutcome.NOT_DEAD

    source.deleted_at = utc_now()
    await async_db.commit()
    gone = await service.redrive(kind=DeadLetterKind.KNOWLEDGE_SYNC, dead_letter_id=failed.id)
    assert gone.outcome is RedriveOutcome.UNSUPPORTED


@pytest.mark.asyncio
async def test_dead_letters_and_redrive_are_scoped_to_the_callers_workspace(async_db, ctx, tenant2_ctx) -> None:
    knowledge, source, remote, worker = await _setup(async_db, ctx)
    failed = await create_sync_run(async_db, source, trigger="manual", requested_by="alice")
    failed.status = "failed"
    failed.finished_at = utc_now()
    await async_db.commit()
    foreign = DeadLetterService(async_db, tenant2_ctx)

    assert await foreign.list_dead_letters(kind=DeadLetterKind.KNOWLEDGE_SYNC) == []
    result = await foreign.redrive(kind=DeadLetterKind.KNOWLEDGE_SYNC, dead_letter_id=failed.id)
    assert result.outcome is RedriveOutcome.NOT_FOUND
    assert (await _fresh(async_db, KnowledgeSyncRun, failed.id)).status == "failed"
