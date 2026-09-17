"""TraceWriter create_run writes transactional outbox rows (Wave B1)."""

from __future__ import annotations

import pytest
from sqlmodel import select

from app.infra.db.transaction import async_transaction
from app.kernel.events.dispatcher import OutboxDispatcher
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run, RunArtifact, RunCostEntry, RunStep
from app.kernel.runtime.runs.writer import TraceWriter
from app.wiring.outbox_handlers import get_outbox_registry, register_outbox_handlers


@pytest.mark.asyncio
async def test_create_run_inserts_outbox_row_same_transaction(async_db, ctx) -> None:
    tw = TraceWriter(async_db, ctx, event_bus=None)
    run = await tw.create_run("integration_mode", kind="test")

    rows = list((await async_db.exec(select(EventOutbox).where(EventOutbox.run_id == run.id))).all())
    assert len(rows) == 1
    assert rows[0].event_type == "run.created"
    assert rows[0].event_id == f"evt_run_created_{run.id}"
    assert rows[0].status == "pending"
    assert rows[0].payload_json.get("run_id") == run.id


@pytest.mark.asyncio
async def test_create_run_and_outbox_roll_back_together(async_db, ctx) -> None:
    writer = TraceWriter(async_db, ctx, event_bus=None)

    with pytest.raises(RuntimeError, match="abort use case"):
        async with async_transaction(async_db):
            run = await writer.create_run("rollback_mode", kind="test")
            raise RuntimeError("abort use case")

    assert await async_db.get(Run, run.id) is None
    rows = list((await async_db.exec(select(EventOutbox).where(EventOutbox.run_id == run.id))).all())
    assert rows == []


@pytest.mark.asyncio
async def test_create_step_and_outbox_roll_back_with_run(async_db, ctx) -> None:
    writer = TraceWriter(async_db, ctx, event_bus=None)

    with pytest.raises(RuntimeError, match="abort use case"):
        async with async_transaction(async_db):
            run = await writer.create_run("rollback_step_mode", kind="test")
            step = await writer.create_step(
                run_id=run.id,
                step_type="other",
            )
            raise RuntimeError("abort use case")

    assert await async_db.get(Run, run.id) is None
    assert await async_db.get(RunStep, step.id) is None
    rows = list((await async_db.exec(select(EventOutbox).where(EventOutbox.run_id == run.id))).all())
    assert rows == []


@pytest.mark.asyncio
async def test_record_cost_and_outbox_roll_back_with_run(async_db, ctx) -> None:
    writer = TraceWriter(async_db, ctx, event_bus=None)

    with pytest.raises(RuntimeError, match="abort use case"):
        async with async_transaction(async_db):
            run = await writer.create_run("rollback_cost_mode", kind="test")
            cost = await writer.record_cost(
                run_id=run.id,
                step_id=None,
                billing_basis="tokens",
                billed_quantity=10,
            )
            raise RuntimeError("abort use case")

    assert await async_db.get(Run, run.id) is None
    assert await async_db.get(RunCostEntry, cost.id) is None
    rows = list((await async_db.exec(select(EventOutbox).where(EventOutbox.run_id == run.id))).all())
    assert rows == []


@pytest.mark.asyncio
async def test_run_status_and_outbox_roll_back_together(async_db, ctx) -> None:
    writer = TraceWriter(async_db, ctx, event_bus=None)
    run = await writer.create_run("rollback_status_mode", kind="test")
    await async_db.commit()

    with pytest.raises(RuntimeError, match="abort use case"):
        async with async_transaction(async_db):
            await writer.update_run_status(run.id, "running")
            raise RuntimeError("abort use case")

    await async_db.refresh(run)
    assert run.status == "queued"
    status_rows = list(
        (await async_db.exec(
            select(EventOutbox).where(
                EventOutbox.run_id == run.id,
                EventOutbox.event_type == "run.status.updated",
            )
        )).all()
    )
    assert status_rows == []


@pytest.mark.asyncio
async def test_step_status_and_outbox_roll_back_together(async_db, ctx) -> None:
    writer = TraceWriter(async_db, ctx, event_bus=None)
    run = await writer.create_run("rollback_step_status_mode", kind="test")
    step = await writer.create_step(run_id=run.id, step_type="other")
    await async_db.commit()

    with pytest.raises(RuntimeError, match="abort use case"):
        async with async_transaction(async_db):
            await writer.update_step_status(step.id, "running")
            raise RuntimeError("abort use case")

    await async_db.refresh(step)
    await async_db.refresh(run)
    assert step.status == "queued"
    status_rows = list(
        (await async_db.exec(
            select(EventOutbox).where(
                EventOutbox.run_id == run.id,
                EventOutbox.event_type == "step.status.updated",
            )
        )).all()
    )
    assert status_rows == []


@pytest.mark.asyncio
async def test_step_metrics_follow_caller_transaction(async_db, ctx) -> None:
    writer = TraceWriter(async_db, ctx, event_bus=None)
    run = await writer.create_run("rollback_step_metrics_mode", kind="test")
    step = await writer.create_step(run_id=run.id, step_type="other")
    await async_db.commit()

    with pytest.raises(RuntimeError, match="abort use case"):
        async with async_transaction(async_db):
            await writer.update_step_metrics(step.id, {"attempt": 2})
            raise RuntimeError("abort use case")

    await async_db.refresh(step)
    assert step.metrics_json in (None, {})


@pytest.mark.asyncio
async def test_artifact_follows_caller_transaction(async_db, ctx) -> None:
    writer = TraceWriter(async_db, ctx, event_bus=None)
    run = await writer.create_run("rollback_artifact_mode", kind="test")
    await async_db.commit()

    with pytest.raises(RuntimeError, match="abort use case"):
        async with async_transaction(async_db):
            artifact = await writer.create_artifact(
                run_id=run.id,
                artifact_type="file",
                storage_key=(
                    f"tenants/{ctx.tenant_id}/workspaces/{ctx.workspace_id}/runs/{run.id}/artifacts/test.txt"
                ),
                size_bytes=4,
                sha256="a" * 64,
            )
            raise RuntimeError("abort use case")

    assert await async_db.get(RunArtifact, artifact.id) is None


@pytest.mark.asyncio
async def test_create_run_outbox_dispatched_to_done(async_db, ctx) -> None:
    register_outbox_handlers()
    tw = TraceWriter(async_db, ctx, event_bus=None)
    run = await tw.create_run("dispatch_mode", kind="test")

    row = (await async_db.exec(select(EventOutbox).where(EventOutbox.run_id == run.id))).first()
    assert row is not None
    assert row.status == "pending"

    d = OutboxDispatcher(async_db, get_outbox_registry())
    n = await d.run_once(batch_limit=10)
    await async_db.commit()
    assert n == 1

    updated = await async_db.get(EventOutbox, row.id)
    assert updated is not None
    assert updated.status == "done"
