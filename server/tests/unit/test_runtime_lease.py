"""Tests for the shared runtime lease primitives and knowledge lease usage."""

import asyncio
from datetime import timedelta

import pytest

from app.kernel.commons.errors import ConflictError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.common import lease
from app.modules.knowledge.domain.models import KnowledgeIngestTask
from app.modules.knowledge.infra.repository import IngestTaskRepository
from app.modules.knowledge.runtime.ingest_worker import GlobalKnowledgeIngestWorker
from app.modules.workflow.domain.models import WorkflowRun
from app.settings.settings import Settings


async def _queued_task(async_db, ctx: RequestContext, *, task_id: str) -> KnowledgeIngestTask:
    task = KnowledgeIngestTask(
        id=task_id,
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        knowledge_id="knw_lease_test",
        document_id=f"doc_{task_id}",
        status="queued",
        created_by=ctx.user_id,
    )
    async_db.add(task)
    await async_db.commit()
    await async_db.refresh(task)
    return task


@pytest.mark.asyncio
async def test_claim_next_takes_queued_task_and_records_lease(async_db, ctx):
    await _queued_task(async_db, ctx, task_id="task_claim_queued")

    claimed = await lease.claim_next(
        async_db,
        KnowledgeIngestTask,
        worker_id="worker-a",
        lease_seconds=60,
    )

    assert claimed is not None
    assert claimed.status == "running"
    assert claimed.lease_owner == "worker-a"
    assert claimed.lease_expires_at is not None
    assert claimed.attempt_count == 1


@pytest.mark.asyncio
async def test_claim_next_skips_task_with_live_lease(async_db, ctx):
    await _queued_task(async_db, ctx, task_id="task_live_lease")
    first = await lease.claim_next(
        async_db,
        KnowledgeIngestTask,
        worker_id="worker-a",
        lease_seconds=600,
    )
    assert first is not None

    second = await lease.claim_next(
        async_db,
        KnowledgeIngestTask,
        worker_id="worker-b",
        lease_seconds=600,
    )

    assert second is None


@pytest.mark.asyncio
async def test_claim_next_reclaims_task_whose_lease_expired(async_db, ctx):
    await _queued_task(async_db, ctx, task_id="task_orphan")
    orphan = await lease.claim_next(
        async_db,
        KnowledgeIngestTask,
        worker_id="worker-crashed",
        lease_seconds=60,
    )
    assert orphan is not None
    # Simulate a worker that died and stopped renewing its lease.
    orphan.lease_expires_at = utc_now() - timedelta(minutes=5)
    async_db.add(orphan)
    await async_db.commit()

    recovered = await lease.claim_next(
        async_db,
        KnowledgeIngestTask,
        worker_id="worker-healthy",
        lease_seconds=60,
    )

    assert recovered is not None
    assert recovered.id == orphan.id
    assert recovered.lease_owner == "worker-healthy"
    assert recovered.attempt_count == 2


@pytest.mark.asyncio
async def test_renew_lease_extends_while_owned(async_db, ctx):
    await _queued_task(async_db, ctx, task_id="task_renew")
    claimed = await lease.claim_next(
        async_db,
        KnowledgeIngestTask,
        worker_id="worker-a",
        lease_seconds=60,
    )
    assert claimed is not None

    outcome = await lease.renew_lease(
        async_db,
        KnowledgeIngestTask,
        claimed.id,
        worker_id="worker-a",
        attempt_count=claimed.attempt_count,
        lease_seconds=60,
    )

    assert outcome is lease.LeaseRenewal.RENEWED


@pytest.mark.asyncio
async def test_renew_lease_reports_loss_after_takeover(async_db, ctx):
    await _queued_task(async_db, ctx, task_id="task_takeover")
    claimed = await lease.claim_next(
        async_db,
        KnowledgeIngestTask,
        worker_id="worker-crashed",
        lease_seconds=60,
    )
    assert claimed is not None
    original_attempt = claimed.attempt_count
    claimed.lease_expires_at = utc_now() - timedelta(minutes=5)
    async_db.add(claimed)
    await async_db.commit()
    await lease.claim_next(
        async_db,
        KnowledgeIngestTask,
        worker_id="worker-healthy",
        lease_seconds=60,
    )

    outcome = await lease.renew_lease(
        async_db,
        KnowledgeIngestTask,
        claimed.id,
        worker_id="worker-crashed",
        attempt_count=original_attempt,
        lease_seconds=60,
    )

    assert outcome is lease.LeaseRenewal.LOST


@pytest.mark.asyncio
async def test_renew_lease_reports_terminal_when_still_owned(async_db, ctx):
    await _queued_task(async_db, ctx, task_id="task_terminal")
    claimed = await lease.claim_next(
        async_db,
        KnowledgeIngestTask,
        worker_id="worker-a",
        lease_seconds=60,
    )
    assert claimed is not None
    claimed.status = "succeeded"
    async_db.add(claimed)
    await async_db.commit()

    outcome = await lease.renew_lease(
        async_db,
        KnowledgeIngestTask,
        claimed.id,
        worker_id="worker-a",
        attempt_count=claimed.attempt_count,
        lease_seconds=60,
    )

    assert outcome is lease.LeaseRenewal.TERMINAL


@pytest.mark.asyncio
async def test_release_lease_clears_owner_and_sets_status(async_db, ctx):
    await _queued_task(async_db, ctx, task_id="task_release")
    claimed = await lease.claim_next(
        async_db,
        KnowledgeIngestTask,
        worker_id="worker-a",
        lease_seconds=60,
    )
    assert claimed is not None

    released = await lease.release_lease(
        async_db,
        KnowledgeIngestTask,
        claimed.id,
        worker_id="worker-a",
        status="succeeded",
    )
    await async_db.refresh(claimed)

    assert released is True
    assert claimed.status == "succeeded"
    assert claimed.lease_owner is None
    assert claimed.lease_expires_at is None


@pytest.mark.asyncio
async def test_holds_lease_tracks_ownership(async_db, ctx):
    await _queued_task(async_db, ctx, task_id="task_holds")
    claimed = await lease.claim_next(
        async_db,
        KnowledgeIngestTask,
        worker_id="worker-a",
        lease_seconds=60,
    )
    assert claimed is not None

    assert await lease.holds_lease(
        async_db,
        KnowledgeIngestTask,
        claimed.id,
        worker_id="worker-a",
        attempt_count=claimed.attempt_count,
    )
    assert not await lease.holds_lease(
        async_db,
        KnowledgeIngestTask,
        claimed.id,
        worker_id="worker-b",
        attempt_count=claimed.attempt_count,
    )


def test_normalize_lease_seconds_enforces_minimum():
    assert lease.normalize_lease_seconds(None) == lease.MIN_LEASE_SECONDS
    assert lease.normalize_lease_seconds(1) == lease.MIN_LEASE_SECONDS
    assert lease.normalize_lease_seconds(300) == 300


def test_heartbeat_interval_renews_several_times_per_lease():
    interval = lease.heartbeat_interval_for(90)

    assert interval < 90
    assert interval == 90 / lease.LEASE_RENEWALS_PER_LEASE


def test_heartbeat_interval_honours_an_explicit_override():
    # Callers that ask for a fast heartbeat get exactly that; clamping the
    # override to the floor would stall tests that drive renewals by hand.
    assert lease.heartbeat_interval_for(90, override=0.01) == 0.01


@pytest.mark.asyncio
async def test_ingest_status_update_releases_lease_on_terminal(async_db, ctx):
    await _queued_task(async_db, ctx, task_id="task_status_terminal")
    repo = IngestTaskRepository(async_db, ctx)
    claimed = await repo.claim_next(worker_id="worker-a", lease_seconds=60)
    assert claimed is not None and claimed.lease_owner == "worker-a"

    updated = await repo.update_status(claimed, "succeeded")

    assert updated.lease_owner is None
    assert updated.lease_expires_at is None


def test_ingest_worker_is_unbounded_by_default_configuration():
    # A bounded shipped default made the long-running worker stop after a
    # handful of documents. Assert the declared default rather than the loaded
    # instance so a developer's local .env cannot mask the regression.
    field = Settings.model_fields["knowledge_ingest_worker_max_tasks"]

    assert field.default == 0


@pytest.mark.asyncio
async def test_ingest_worker_loop_keeps_running_without_a_task_limit(monkeypatch):
    worker = GlobalKnowledgeIngestWorker(db_factory=lambda: None)
    processed = KnowledgeIngestTask(
        tenant_id="tenant_loop",
        workspace_id="workspace_loop",
        knowledge_id="knw_loop",
    )
    calls = {"count": 0}

    async def _run_once():
        calls["count"] += 1
        return processed

    monkeypatch.setattr(worker, "run_once", _run_once)

    with pytest.raises((TimeoutError, asyncio.TimeoutError)):
        await asyncio.wait_for(
            worker.run_loop(poll_interval=0, max_tasks=None),
            timeout=0.5,
        )

    assert calls["count"] > 10


@pytest.mark.asyncio
async def test_ingest_worker_loop_still_honours_an_explicit_limit(monkeypatch):
    worker = GlobalKnowledgeIngestWorker(db_factory=lambda: None)
    processed = KnowledgeIngestTask(
        tenant_id="tenant_bounded",
        workspace_id="workspace_bounded",
        knowledge_id="knw_bounded",
    )
    calls = {"count": 0}

    async def _run_once():
        calls["count"] += 1
        return processed

    monkeypatch.setattr(worker, "run_once", _run_once)

    total = await worker.run_loop(poll_interval=0, max_tasks=3)

    assert total == 3
    assert calls["count"] == 3


@pytest.mark.asyncio
async def test_workflow_runs_are_claimable_and_reclaimable(async_db, ctx):
    # Workflow executions carry their own snapshot so a worker can run them
    # without the originating request.
    run = WorkflowRun(
        id="wfr_lease",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        run_id="run_wf_lease",
        workflow_id="wf_lease",
        status="queued",
        inputs_json={"topic": "leases"},
        request_context_json={
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "user_id": ctx.user_id,
        },
    )
    async_db.add(run)
    await async_db.commit()

    claimed = await lease.claim_next(
        async_db,
        WorkflowRun,
        worker_id="wf-worker-a",
        lease_seconds=60,
    )
    assert claimed is not None
    assert claimed.lease_owner == "wf-worker-a"
    assert claimed.attempt_count == 1
    assert claimed.inputs_json == {"topic": "leases"}
    assert claimed.request_context_json["tenant_id"] == ctx.tenant_id

    assert (
        await lease.claim_next(async_db, WorkflowRun, worker_id="wf-worker-b", lease_seconds=60)
        is None
    )

    claimed.lease_expires_at = utc_now() - timedelta(minutes=5)
    async_db.add(claimed)
    await async_db.commit()

    recovered = await lease.claim_next(
        async_db,
        WorkflowRun,
        worker_id="wf-worker-b",
        lease_seconds=60,
    )
    assert recovered is not None
    assert recovered.id == "wfr_lease"
    assert recovered.lease_owner == "wf-worker-b"
    assert recovered.attempt_count == 2


@pytest.mark.asyncio
async def test_requeued_ingest_task_is_claimable_again(async_db, ctx):
    await _queued_task(async_db, ctx, task_id="task_status_requeue")
    repo = IngestTaskRepository(async_db, ctx)
    claimed = await repo.claim_next(worker_id="worker-a", lease_seconds=600)
    assert claimed is not None

    await repo.update_status(claimed, "queued", retry_count=1)
    reclaimed = await repo.claim_next(worker_id="worker-b", lease_seconds=600)

    assert reclaimed is not None
    assert reclaimed.id == claimed.id
    assert reclaimed.lease_owner == "worker-b"


@pytest.mark.asyncio
async def test_terminal_write_is_refused_after_the_lease_is_reclaimed(async_db, ctx):
    await _queued_task(async_db, ctx, task_id="task_lease_guard")
    repo = IngestTaskRepository(async_db, ctx)
    claimed = await repo.claim_next(worker_id="worker-a", lease_seconds=60)
    assert claimed is not None

    # Another worker reclaims the task while the first is still working.
    claimed.lease_expires_at = utc_now() - timedelta(minutes=5)
    async_db.add(claimed)
    await async_db.commit()
    reclaimed = await lease.claim_next(
        async_db,
        KnowledgeIngestTask,
        worker_id="worker-b",
        lease_seconds=60,
    )
    assert reclaimed is not None and reclaimed.lease_owner == "worker-b"

    # The superseded worker must not record an outcome over the owner's.
    with pytest.raises(ConflictError):
        await repo.update_status(claimed, "succeeded", expected_lease_owner="worker-a")

    await async_db.refresh(claimed)
    assert claimed.status == "running"
    assert claimed.lease_owner == "worker-b"


@pytest.mark.asyncio
async def test_the_lease_holder_can_still_write_its_terminal_status(async_db, ctx):
    await _queued_task(async_db, ctx, task_id="task_lease_holder")
    repo = IngestTaskRepository(async_db, ctx)
    claimed = await repo.claim_next(worker_id="worker-a", lease_seconds=60)
    assert claimed is not None

    updated = await repo.update_status(claimed, "succeeded", expected_lease_owner="worker-a")

    assert updated.status == "succeeded"
    assert updated.lease_owner is None


@pytest.mark.asyncio
async def test_an_unguarded_status_write_still_works(async_db, ctx):
    # Callers outside the worker (cancel, requeue) have no lease to prove.
    await _queued_task(async_db, ctx, task_id="task_unguarded")
    repo = IngestTaskRepository(async_db, ctx)

    updated = await repo.update_status(
        await repo.claim_next(worker_id="worker-a", lease_seconds=60),
        "canceled",
    )

    assert updated.status == "canceled"
