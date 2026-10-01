"""Knowledge connector sync engine: change detection, removals, caps, runs."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.kernel.commons.errors import ConflictError
from app.kernel.commons.time import utc_now
from app.kernel.ports.connectors import ConnectorError
from app.kernel.runtime.db.models.audit import AuditEvent
from app.modules.knowledge.application.connector_sync import (
    KnowledgeSyncEngine,
    SyncLimits,
    connector_doc_key,
    create_sync_run,
    enqueue_due_runs,
)
from app.modules.knowledge.application.runtime_schemas import KnowledgeCreate
from app.modules.knowledge.domain.models import (
    Knowledge,
    KnowledgeDocument,
    KnowledgeSource,
    KnowledgeSourceItem,
    KnowledgeSyncRun,
)
from app.modules.knowledge.runtime.ingest_worker import KnowledgeIngestWorker
from tests.unit.knowledge_connector_support import (
    FakeRemote,
    FakeSecretsPort,
    build_registry,
)
from tests.unit.test_knowledge_runtime_service import build_knowledge_test_service


async def _setup(async_db, ctx, *, with_index: bool = True, secrets=None, secret_requirement: str = "none", **source_kwargs):
    service, storage, _vector = build_knowledge_test_service(async_db, ctx)
    knowledge = await service.create_knowledge(
        KnowledgeCreate(
            name="kb_sync",
            type="document",
            default_embedding_model_ref="model:test:embedding" if with_index else None,
        )
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
    engine = KnowledgeSyncEngine(
        db=async_db,
        ctx=ctx,
        runtime=service,
        registry=build_registry(remote, secret=secret_requirement),
        secrets_port=secrets,
    )
    return service, knowledge, source, remote, engine


async def _sync(async_db, engine, source, *, trigger: str = "manual") -> KnowledgeSyncRun:
    run = await create_sync_run(async_db, source, trigger=trigger, requested_by="test-user")
    return await engine.execute(run)


async def _documents(async_db, knowledge_id: str) -> list[KnowledgeDocument]:
    rows = (
        await async_db.exec(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.knowledge_id == knowledge_id)
            .order_by(KnowledgeDocument.doc_key, KnowledgeDocument.version)
        )
    ).scalars().all()
    return list(rows)


async def _items(async_db, source_id: str) -> dict[str, KnowledgeSourceItem]:
    rows = (
        await async_db.exec(select(KnowledgeSourceItem).where(KnowledgeSourceItem.source_id == source_id))
    ).scalars().all()
    return {row.external_id: row for row in rows}


@pytest.mark.asyncio
async def test_first_sync_ingests_every_item_as_a_connector_document(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx)
    remote.put("docs/a.txt", b"alpha document")
    remote.put("docs/b.md", b"# beta", content_type="text/markdown")

    run = await _sync(async_db, engine, source)

    assert run.status == "succeeded"
    assert (run.added_count, run.updated_count, run.unchanged_count, run.failed_count) == (2, 0, 0, 0)
    documents = await _documents(async_db, knowledge.id)
    assert len(documents) == 2
    by_external = {doc.external_id: doc for doc in documents}
    doc = by_external["docs/a.txt"]
    assert doc.source_kind == "connector"
    assert doc.source_uri == "fake://bucket/docs/a.txt"
    assert doc.doc_key == connector_doc_key(source.id, "docs/a.txt")
    assert doc.content_hash and doc.checksum == doc.content_hash
    assert doc.mime_type == "text/plain" and by_external["docs/b.md"].mime_type == "text/markdown"
    assert doc.created_by == ctx.user_id

    items = await _items(async_db, source.id)
    assert set(items) == {"docs/a.txt", "docs/b.md"}
    assert items["docs/a.txt"].document_id == doc.id and items["docs/a.txt"].status == "present"

    refreshed = await async_db.get(KnowledgeSource, source.id)
    assert refreshed.last_status == "succeeded"
    assert refreshed.last_counts_json["added"] == 2


@pytest.mark.asyncio
async def test_documents_are_indexed_by_the_ingest_worker(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx)
    remote.put("a.txt", b"searchable text about refunds")

    await _sync(async_db, engine, source)
    worker = KnowledgeIngestWorker(service)
    await worker.run_once()

    documents = await _documents(async_db, knowledge.id)
    assert [doc.status for doc in documents] == ["indexed"]


@pytest.mark.asyncio
async def test_second_sync_of_an_unchanged_remote_does_nothing(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx)
    remote.put("a.txt", b"one")
    remote.put("b.txt", b"two")
    await _sync(async_db, engine, source)
    remote.fetches.clear()

    run = await _sync(async_db, engine, source)

    assert run.status == "succeeded"
    assert (run.added_count, run.updated_count, run.unchanged_count) == (0, 0, 2)
    assert remote.fetches == []
    assert len(await _documents(async_db, knowledge.id)) == 2
    assert set(remote.seen_known) == {"a.txt", "b.txt"}


@pytest.mark.asyncio
async def test_changed_content_becomes_a_new_version_of_the_same_document(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx)
    remote.put("a.txt", b"first draft", etag="e1")
    await _sync(async_db, engine, source)

    remote.put("a.txt", b"second draft", etag="e2")
    run = await _sync(async_db, engine, source)

    assert (run.added_count, run.updated_count, run.unchanged_count) == (0, 1, 0)
    documents = await _documents(async_db, knowledge.id)
    assert [(doc.version, doc.is_latest) for doc in documents] == [(1, False), (2, True)]
    assert documents[0].doc_key == documents[1].doc_key
    item = (await _items(async_db, source.id))["a.txt"]
    assert item.document_id == documents[1].id and item.remote_etag == "e2"


@pytest.mark.asyncio
async def test_new_etag_with_identical_bytes_is_unchanged_by_content_hash(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx)
    remote.put("a.txt", b"same bytes", etag="e1")
    await _sync(async_db, engine, source)

    remote.put("a.txt", b"same bytes", etag="e2")
    run = await _sync(async_db, engine, source)

    assert (run.added_count, run.updated_count, run.unchanged_count) == (0, 0, 1)
    assert remote.fetches.count("a.txt") == 2
    assert len(await _documents(async_db, knowledge.id)) == 1
    assert (await _items(async_db, source.id))["a.txt"].remote_etag == "e2"

    # The new marker is remembered, so the next run does not download again.
    remote.fetches.clear()
    await _sync(async_db, engine, source)
    assert remote.fetches == []


@pytest.mark.asyncio
async def test_modified_marker_is_used_when_the_remote_has_no_etag(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx)
    remote.put("page", b"hello", etag="", modified="Mon, 01 Jan 2026 00:00:00 GMT")
    for obj in remote.objects.values():
        obj.etag = ""
    await _sync(async_db, engine, source)
    remote.fetches.clear()

    run = await _sync(async_db, engine, source)

    assert run.unchanged_count == 1
    assert remote.fetches == []


@pytest.mark.asyncio
async def test_removed_item_deletes_its_documents_when_the_source_asks(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx, delete_removed=True)
    remote.put("a.txt", b"keep", etag="k")
    remote.put("b.txt", b"v1", etag="b1")
    await _sync(async_db, engine, source)
    remote.put("b.txt", b"v2", etag="b2")
    await _sync(async_db, engine, source)
    del remote.objects["b.txt"]

    run = await _sync(async_db, engine, source)

    assert run.status == "succeeded"
    assert run.removed_count == 1 and run.unchanged_count == 1
    live = [doc for doc in await _documents(async_db, knowledge.id) if doc.deleted_at is None]
    assert [doc.external_id for doc in live] == ["a.txt"]
    items = await _items(async_db, source.id)
    assert items["b.txt"].status == "removed" and items["b.txt"].document_id is None
    assert items["a.txt"].status == "present"
    refreshed = await async_db.get(Knowledge, knowledge.id)
    assert refreshed.doc_count == 1


@pytest.mark.asyncio
async def test_removed_item_keeps_its_document_by_default_and_revives_when_it_returns(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx)
    remote.put("a.txt", b"content", etag="e1")
    await _sync(async_db, engine, source)
    saved = remote.objects.pop("a.txt")

    run = await _sync(async_db, engine, source)

    assert run.removed_count == 1
    assert run.outcomes_json[0]["detail"] == "document kept"
    docs = await _documents(async_db, knowledge.id)
    assert len(docs) == 1 and docs[0].deleted_at is None
    assert (await _items(async_db, source.id))["a.txt"].status == "removed"

    remote.objects["a.txt"] = saved
    remote.fetches.clear()
    run = await _sync(async_db, engine, source)

    assert (run.added_count, run.unchanged_count) == (0, 1)
    assert remote.fetches == []
    assert (await _items(async_db, source.id))["a.txt"].status == "present"


@pytest.mark.asyncio
async def test_item_that_returns_after_its_document_was_deleted_is_ingested_again(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx, delete_removed=True)
    remote.put("a.txt", b"content", etag="e1")
    await _sync(async_db, engine, source)
    saved = remote.objects.pop("a.txt")
    await _sync(async_db, engine, source)

    remote.objects["a.txt"] = saved
    run = await _sync(async_db, engine, source)

    assert run.added_count == 1
    live = [doc for doc in await _documents(async_db, knowledge.id) if doc.deleted_at is None]
    assert len(live) == 1 and live[0].version == 2 and live[0].is_latest


@pytest.mark.asyncio
async def test_document_deleted_by_a_user_is_recreated_while_it_exists_remotely(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx)
    remote.put("a.txt", b"content", etag="e1")
    await _sync(async_db, engine, source)
    document = (await _documents(async_db, knowledge.id))[0]
    await service.delete_document(document.id)

    run = await _sync(async_db, engine, source)

    assert run.added_count == 1
    live = [doc for doc in await _documents(async_db, knowledge.id) if doc.deleted_at is None]
    assert len(live) == 1 and live[0].id != document.id


@pytest.mark.asyncio
async def test_one_failing_item_makes_the_run_partial_and_is_retried_next_time(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx)
    remote.put("good.txt", b"fine")
    remote.put("bad.txt", b"broken", fail_fetch="access denied")

    run = await _sync(async_db, engine, source)

    assert run.status == "partial"
    assert (run.added_count, run.failed_count) == (1, 1)
    assert run.outcomes_json == [
        {"external_id": "bad.txt", "name": "bad.txt", "outcome": "failed", "error": "access denied"},
        {"external_id": "good.txt", "name": "good.txt", "outcome": "added"},
    ]
    items = await _items(async_db, source.id)
    assert items["bad.txt"].status == "failed" and items["bad.txt"].last_error == "access denied"
    assert items["good.txt"].status == "present"
    assert (await async_db.get(KnowledgeSource, source.id)).last_status == "partial"

    remote.objects["bad.txt"].fail_fetch = None
    run = await _sync(async_db, engine, source)

    assert run.status == "succeeded"
    assert (run.added_count, run.unchanged_count) == (1, 1)
    assert (await _items(async_db, source.id))["bad.txt"].status == "present"


@pytest.mark.asyncio
async def test_item_the_connector_reports_as_unreadable_is_failed_never_removed(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx, delete_removed=True)
    remote.put("a.txt", b"content", etag="e1")
    await _sync(async_db, engine, source)
    remote.objects["a.txt"].list_error = "temporary failure"

    run = await _sync(async_db, engine, source)

    assert run.status == "partial" and run.failed_count == 1 and run.removed_count == 0
    live = [doc for doc in await _documents(async_db, knowledge.id) if doc.deleted_at is None]
    assert len(live) == 1


@pytest.mark.asyncio
async def test_listing_failure_fails_the_run_and_deletes_nothing(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx, delete_removed=True)
    remote.put("a.txt", b"one")
    remote.put("b.txt", b"two")
    await _sync(async_db, engine, source)

    remote.list_failure = ConnectorError(ConnectorError.AUTH_FAILED, "The credentials were rejected")
    run = await _sync(async_db, engine, source)

    assert run.status == "failed"
    assert run.error_code == ConnectorError.AUTH_FAILED
    assert run.error_message == "The credentials were rejected"
    assert run.removed_count == 0
    live = [doc for doc in await _documents(async_db, knowledge.id) if doc.deleted_at is None]
    assert len(live) == 2
    refreshed = await async_db.get(KnowledgeSource, source.id)
    assert refreshed.last_status == "failed" and refreshed.last_error == "The credentials were rejected"


@pytest.mark.asyncio
async def test_listing_that_breaks_part_way_never_removes_unseen_items(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx, delete_removed=True)
    for key in ("a.txt", "b.txt", "c.txt"):
        remote.put(key, key.encode())
    await _sync(async_db, engine, source)

    remote.fail_after = 1
    run = await _sync(async_db, engine, source)

    assert run.status == "failed" and run.removed_count == 0
    live = [doc for doc in await _documents(async_db, knowledge.id) if doc.deleted_at is None]
    assert len(live) == 3


@pytest.mark.asyncio
async def test_item_cap_truncates_the_listing_and_skips_removals(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(
        async_db, ctx, delete_removed=True, limits_json={"max_items": 2}
    )
    for key in ("a.txt", "b.txt", "c.txt"):
        remote.put(key, key.encode())
    await _sync(async_db, engine, source)
    assert len(await _items(async_db, source.id)) == 2

    # With more items than the cap the listing is cut off, so an item missing
    # from the part that was read is not taken to be removed.
    del remote.objects["a.txt"]
    remote.put("d.txt", b"d")
    run = await _sync(async_db, engine, source)

    assert run.truncated is True
    assert run.removed_count == 0
    live = [doc for doc in await _documents(async_db, knowledge.id) if doc.deleted_at is None]
    assert {doc.external_id for doc in live} == {"a.txt", "b.txt", "c.txt"}
    refreshed = await async_db.get(KnowledgeSource, source.id)
    assert refreshed.last_counts_json["truncated"] is True


@pytest.mark.asyncio
async def test_oversized_item_fails_without_being_downloaded(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(
        async_db, ctx, limits_json={"max_item_bytes": 10}
    )
    remote.put("big.txt", b"x" * 50)
    remote.put("small.txt", b"tiny")

    run = await _sync(async_db, engine, source)

    assert run.status == "partial" and run.added_count == 1 and run.failed_count == 1
    assert "big.txt" not in remote.fetches
    assert "byte limit" in run.outcomes_json[0]["error"]


@pytest.mark.asyncio
async def test_total_byte_cap_stops_the_run_early(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(
        async_db, ctx, delete_removed=True, limits_json={"max_total_bytes": 12}
    )
    remote.put("a.txt", b"12345678")
    remote.put("b.txt", b"12345678")
    remote.put("c.txt", b"12345678")

    run = await _sync(async_db, engine, source)

    assert run.truncated is True
    assert run.added_count == 1
    assert run.removed_count == 0


@pytest.mark.asyncio
async def test_empty_item_is_a_failure(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx)
    remote.put("empty.txt", b"")

    run = await _sync(async_db, engine, source)

    assert run.failed_count == 1 and run.status == "partial"


@pytest.mark.asyncio
async def test_a_second_active_run_for_the_same_source_is_refused(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx)
    first = await create_sync_run(async_db, source, trigger="manual", requested_by="u")

    with pytest.raises(ConflictError):
        await create_sync_run(async_db, source, trigger="manual", requested_by="u")

    first.status = "succeeded"
    await async_db.commit()
    second = await create_sync_run(async_db, source, trigger="manual", requested_by="u")
    assert second.id != first.id


@pytest.mark.asyncio
async def test_cancel_request_ends_the_run_as_canceled(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx)
    remote.put("a.txt", b"one")
    run = await create_sync_run(async_db, source, trigger="manual", requested_by="u")
    run.cancel_requested = True
    await async_db.commit()

    run = await engine.execute(run)

    assert run.status == "canceled"
    assert run.finished_at is not None
    assert (await async_db.get(KnowledgeSource, source.id)).last_status == "canceled"
    assert await _documents(async_db, knowledge.id) == []


@pytest.mark.asyncio
async def test_a_worker_that_lost_its_lease_discards_its_outcome(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx)
    remote.put("a.txt", b"one")
    run = await create_sync_run(async_db, source, trigger="manual", requested_by="u")
    run.status = "running"
    run.lease_owner = "someone-else"
    await async_db.commit()

    with pytest.raises(ConflictError):
        await engine.execute(run, lease_owner="stale-worker")

    assert run.status == "running"


@pytest.mark.asyncio
async def test_sync_fails_clearly_when_the_knowledge_base_has_no_index(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx, with_index=False)
    remote.put("a.txt", b"one")

    run = await _sync(async_db, engine, source)

    assert run.status == "failed"
    assert "no index" in run.error_message


@pytest.mark.asyncio
async def test_secret_is_resolved_once_and_handed_to_the_connector_only(async_db, ctx) -> None:
    secrets = FakeSecretsPort({"sec_s3key": '{"access_key_id": "AKIA", "secret_access_key": "hunter2"}'})
    service, knowledge, source, remote, engine = await _setup(
        async_db, ctx, secrets=secrets, secret_requirement="required", secret_id="sec_s3key"
    )
    remote.put("a.txt", b"one")

    run = await _sync(async_db, engine, source)

    assert run.status == "succeeded"
    assert secrets.requested == ["sec_s3key"]
    assert remote.built_with == [({"bucket": "docs"}, '{"access_key_id": "AKIA", "secret_access_key": "hunter2"}')]
    stored = (await async_db.get(KnowledgeSource, source.id)).model_dump_json()
    assert "hunter2" not in stored


@pytest.mark.asyncio
async def test_unreadable_secret_fails_the_run_without_echoing_anything(async_db, ctx) -> None:
    secrets = FakeSecretsPort({})
    service, knowledge, source, remote, engine = await _setup(
        async_db, ctx, secrets=secrets, secret_requirement="required", secret_id="sec_gone"
    )

    run = await _sync(async_db, engine, source)

    assert run.status == "failed"
    assert run.error_code == ConnectorError.CREDENTIALS_INVALID
    assert "sec_gone" not in (run.error_message or "")


@pytest.mark.asyncio
async def test_required_secret_missing_fails_the_run(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx, secret_requirement="required")

    run = await _sync(async_db, engine, source)

    assert run.status == "failed" and run.error_code == ConnectorError.CREDENTIALS_INVALID


@pytest.mark.asyncio
async def test_run_for_a_source_of_another_workspace_is_not_executed(async_db, ctx, tenant2_ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx)
    remote.put("a.txt", b"one")
    foreign_service, *_ = build_knowledge_test_service(async_db, tenant2_ctx)
    foreign_engine = KnowledgeSyncEngine(
        db=async_db,
        ctx=tenant2_ctx,
        runtime=foreign_service,
        registry=build_registry(remote),
    )
    run = await create_sync_run(async_db, source, trigger="manual", requested_by="u")

    run = await foreign_engine.execute(run)

    assert run.status == "failed" and run.error_code == "NOT_FOUND"
    assert remote.fetches == []


@pytest.mark.asyncio
async def test_sync_writes_started_and_finished_audit_events(async_db, ctx) -> None:
    service, knowledge, source, remote, engine = await _setup(async_db, ctx)
    remote.put("a.txt", b"one")

    run = await _sync(async_db, engine, source)

    events = (
        await async_db.exec(select(AuditEvent).where(AuditEvent.resource_id == source.id).order_by(AuditEvent.created_at))
    ).scalars().all()
    assert [event.event_type for event in events] == [
        "knowledge.source.sync.started",
        "knowledge.source.sync.finished",
    ]
    assert events[1].outcome == "succeeded" and events[1].payload_json["run_id"] == run.id
    assert events[1].tenant_id == ctx.tenant_id and events[1].workspace_id == ctx.workspace_id


@pytest.mark.asyncio
async def test_enqueue_due_runs_queues_only_due_enabled_sources_and_advances_the_schedule(async_db, ctx) -> None:
    now = utc_now()
    service, knowledge, source, remote, engine = await _setup(
        async_db,
        ctx,
        schedule_cron="0 * * * *",
        next_sync_at=now - timedelta(minutes=1),
    )
    not_due = KnowledgeSource(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        knowledge_id=knowledge.id,
        name="later",
        connector_kind="fake",
        schedule_cron="0 * * * *",
        next_sync_at=now + timedelta(hours=1),
    )
    disabled = KnowledgeSource(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        knowledge_id=knowledge.id,
        name="off",
        connector_kind="fake",
        enabled=False,
        schedule_cron="0 * * * *",
        next_sync_at=now - timedelta(minutes=5),
    )
    async_db.add_all([not_due, disabled])
    await async_db.commit()

    queued = await enqueue_due_runs(async_db, now=now)

    assert queued == 1
    runs = (await async_db.exec(select(KnowledgeSyncRun))).scalars().all()
    assert [(run.source_id, run.trigger, run.status, run.requested_by) for run in runs] == [
        (source.id, "schedule", "queued", None)
    ]
    refreshed = await async_db.get(KnowledgeSource, source.id)
    next_sync = refreshed.next_sync_at.replace(tzinfo=None) if refreshed.next_sync_at.tzinfo else refreshed.next_sync_at
    assert next_sync > now.replace(tzinfo=None) and next_sync.minute == 0

    # Due again while the first run is still queued: the firing is skipped, not stacked.
    refreshed.next_sync_at = now - timedelta(seconds=1)
    await async_db.commit()
    assert await enqueue_due_runs(async_db, now=now) == 0
    assert len((await async_db.exec(select(KnowledgeSyncRun))).scalars().all()) == 1
    advanced = (await async_db.get(KnowledgeSource, source.id)).next_sync_at
    assert advanced.replace(tzinfo=None) > now.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_enqueue_due_runs_skips_sources_of_a_deleted_knowledge_base(async_db, ctx) -> None:
    now = utc_now()
    service, knowledge, source, remote, engine = await _setup(
        async_db, ctx, schedule_cron="0 * * * *", next_sync_at=now - timedelta(minutes=1)
    )
    stored = await async_db.get(Knowledge, knowledge.id)
    stored.deleted_at = now
    await async_db.commit()

    assert await enqueue_due_runs(async_db, now=now) == 0


def test_limits_default_and_clamp_to_the_deployment_ceilings() -> None:
    defaults = SyncLimits.from_json(None)
    assert defaults.max_items == 1000 and defaults.max_item_bytes == 5 * 1024 * 1024

    clamped = SyncLimits.from_json({"max_items": 10**9, "max_item_bytes": 10**12, "max_total_bytes": "oops"})
    assert clamped.max_items == 20000
    assert clamped.max_item_bytes == 50 * 1024 * 1024
    assert clamped.max_total_bytes == 256 * 1024 * 1024
