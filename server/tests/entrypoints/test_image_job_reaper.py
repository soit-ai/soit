"""An image run lost with the process that ran it fails, and its call is charged.

Image jobs run in the process that accepted them. A job in progress marks its
run alive; a run nobody has marked alive for long enough was lost, and would
otherwise stay queued or running for good. The reaper fails it, and a model
step it finds still running was a provider call in flight, which the provider
does not cancel: that step is charged the images it asked for, as an estimate.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel import select

from app.kernel.commons.time import utc_now
from app.kernel.runtime.db.models.runs import Run, RunCostEntry
from app.kernel.runtime.runs.writer import TraceWriter
from app.wiring import get_container, image_job
from app.wiring.image_job import (
    INTERRUPTED_ERROR_CODE,
    keep_image_run_alive,
    reap_interrupted_image_runs,
)

_NOTE = {
    "requested_images": 2,
    "image_edit": False,
    "model": "vmodel:painter",
    "model_ref": "model:painter:gpt-image-1",
    "provider_id": "prov_painter",
    "provider_slug": "painter",
    "provider_kind": "openai",
}
_PRICED = SimpleNamespace(pricing={"currency": "USD", "image": "0.04"}, target=None)


class _Describer:
    """Prices every route at 0.04 USD an image and records what it was asked."""

    def __init__(self, route: Any = _PRICED) -> None:
        self.route = route
        self.asked: list[tuple[str, str]] = []

    async def __call__(self, _ctx: Any, model_ref: str, capability: str) -> Any:
        self.asked.append((model_ref, capability))
        return self.route


async def _image_run(async_db, ctx, *, status: str = "running", idle: timedelta = timedelta(hours=1), kind: str = "image"):
    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run("image" if kind == "image" else "chat")
    run.kind = kind
    if status != "queued":
        await writer.update_run_status(run.id, status)
    run = await async_db.get(Run, run.id)
    run.updated_at = utc_now() - idle
    async_db.add(run)
    await async_db.commit()
    return run


async def _step(async_db, ctx, run_id: str, metrics: dict[str, Any] | None, *, step_type: str = "llm", status: str = "running"):
    writer = TraceWriter(async_db, ctx)
    step = await writer.create_step(run_id=run_id, step_type=step_type, status="running")
    if status != "running":
        step = await writer.update_step_status(step.id, status, error_code="IMAGE_ERROR")
    step.metrics_json = metrics
    async_db.add(step)
    await async_db.commit()
    return step


async def _reap(async_db, describe: Any = None) -> int:
    reaped = await reap_interrupted_image_runs(async_db, orphan_after_seconds=600, describe_route=describe or _Describer())
    # What the reaper did must hold once its own session is gone.
    await async_db.rollback()
    return reaped


async def _costs(async_db, run_id: str) -> list[RunCostEntry]:
    return list((await async_db.exec(select(RunCostEntry).where(RunCostEntry.run_id == run_id))).all())


class TestTheReaper:
    @pytest.mark.asyncio
    async def test_a_lost_queued_job_fails_and_bills_nothing(self, async_db, ctx):
        run = await _image_run(async_db, ctx, status="queued")

        assert await _reap(async_db) == 1

        await async_db.refresh(run)
        assert run.status == "failed"
        assert run.error_code == INTERRUPTED_ERROR_CODE
        assert await _costs(async_db, run.id) == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("edit", "operation", "capability"),
        [(False, "generate_image", "image_generation"), (True, "edit_image", "image_edit")],
    )
    async def test_a_call_left_in_flight_is_charged_the_images_it_asked_for(self, async_db, ctx, edit, operation, capability):
        run = await _image_run(async_db, ctx)
        step = await _step(async_db, ctx, run.id, {**_NOTE, "image_edit": edit})
        describe = _Describer()

        await _reap(async_db, describe)

        await async_db.refresh(run)
        await async_db.refresh(step)
        assert run.status == "failed"
        assert run.error_code == INTERRUPTED_ERROR_CODE
        assert run.error_step_id == step.id
        assert step.status == "failed"
        assert step.metrics_json["usage_estimated"] is True
        assert "image_count" not in step.metrics_json
        assert describe.asked == [("model:painter:gpt-image-1", capability)]
        (charge,) = await _costs(async_db, run.id)
        assert charge.step_id == step.id
        assert charge.billing_basis == "images"
        assert charge.billed_quantity == 2
        assert charge.request_count == 2
        assert charge.operation == operation
        assert charge.currency == "USD"
        assert Decimal(str(charge.amount)) == Decimal("0.08")
        assert charge.pricing_snapshot_json["usage_estimated"] is True
        assert charge.pricing_snapshot_json["usage_estimate_basis"] == "requested_images"
        assert charge.pricing_snapshot_json["model"]["requested"] == "vmodel:painter"
        assert charge.model_ref == "model:painter:gpt-image-1"

    @pytest.mark.asyncio
    async def test_a_call_left_in_flight_is_charged_at_the_price_of_what_it_asked_for(self, async_db, ctx):
        run = await _image_run(async_db, ctx)
        await _step(async_db, ctx, run.id, {**_NOTE, "image_size": "1536x1024", "image_quality": "high"})
        priced = SimpleNamespace(
            pricing={
                "currency": "USD",
                "image": "0.042",
                "image_variants": [{"quality": "high", "size": "1536x1024", "price": "0.25"}],
            },
            target=None,
        )

        await _reap(async_db, _Describer(route=priced))

        (charge,) = await _costs(async_db, run.id)
        assert Decimal(str(charge.amount)) == Decimal("0.50")
        assert charge.pricing_snapshot_json["image_variant"] == {"quality": "high", "size": "1536x1024"}
        quantities = charge.pricing_snapshot_json["quantities"]
        assert (quantities["size"], quantities["quality"]) == ("1536x1024", "high")

    @pytest.mark.asyncio
    async def test_a_call_whose_route_is_gone_is_charged_unpriced_to_who_served_it(self, async_db, ctx):
        run = await _image_run(async_db, ctx)
        await _step(async_db, ctx, run.id, {**_NOTE, "requested_images": 1})

        await _reap(async_db, _Describer(route=None))

        (charge,) = await _costs(async_db, run.id)
        assert charge.billed_quantity == 1
        assert charge.amount is None
        assert charge.pricing_snapshot_json["priced"] is False
        assert charge.pricing_snapshot_json["reason"] == "route_not_resolved"
        assert charge.pricing_snapshot_json["usage_estimated"] is True
        assert (charge.model_ref, charge.provider_id, charge.provider_slug, charge.provider_kind) == (
            "model:painter:gpt-image-1",
            "prov_painter",
            "painter",
            "openai",
        )

    @pytest.mark.asyncio
    async def test_a_step_already_charged_is_not_charged_again(self, async_db, ctx):
        run = await _image_run(async_db, ctx)
        step = await _step(async_db, ctx, run.id, _NOTE)
        await TraceWriter(async_db, ctx).record_cost(
            run_id=run.id, step_id=step.id, billing_basis="images", billed_quantity=2, source_port="llm"
        )
        await async_db.commit()

        await _reap(async_db)

        await async_db.refresh(run)
        assert run.status == "failed"
        assert len(await _costs(async_db, run.id)) == 1

    @pytest.mark.asyncio
    async def test_only_a_model_call_still_in_flight_is_charged(self, async_db, ctx):
        # A call that already failed at the provider, or a storage write, cost
        # no images; they are closed, not charged.
        run = await _image_run(async_db, ctx)
        failed_call = await _step(async_db, ctx, run.id, _NOTE, status="failed")
        storage = await _step(async_db, ctx, run.id, _NOTE, step_type="io")
        # Failing a step touches its run; age it again.
        run = await async_db.get(Run, run.id)
        run.updated_at = utc_now() - timedelta(hours=1)
        async_db.add(run)
        await async_db.commit()

        await _reap(async_db)

        await async_db.refresh(storage)
        await async_db.refresh(failed_call)
        assert storage.status == "failed"
        assert storage.error_code == INTERRUPTED_ERROR_CODE
        assert failed_call.error_code != INTERRUPTED_ERROR_CODE
        assert await _costs(async_db, run.id) == []

    @pytest.mark.asyncio
    async def test_a_step_that_never_said_what_it_asked_for_is_not_charged(self, async_db, ctx):
        # Started by a process from before the call was noted on its step.
        run = await _image_run(async_db, ctx)
        step = await _step(async_db, ctx, run.id, None)

        await _reap(async_db)

        await async_db.refresh(step)
        assert step.status == "failed"
        assert step.error_code == INTERRUPTED_ERROR_CODE
        assert await _costs(async_db, run.id) == []

    @pytest.mark.asyncio
    async def test_one_run_that_cannot_be_reaped_does_not_hold_back_the_rest(self, async_db, ctx):
        broken = await _image_run(async_db, ctx, idle=timedelta(hours=2))
        await _step(async_db, ctx, broken.id, {**_NOTE, "model_ref": "model:broken:m"})
        fine = await _image_run(async_db, ctx)
        await _step(async_db, ctx, fine.id, _NOTE)

        async def describe(ctx_: Any, model_ref: str, capability: str) -> Any:
            if model_ref == "model:broken:m":
                raise RuntimeError("configuration no longer reads")
            return await _Describer()(ctx_, model_ref, capability)

        assert await _reap(async_db, describe) == 1

        await async_db.refresh(broken)
        await async_db.refresh(fine)
        assert broken.status == "running"
        assert await _costs(async_db, broken.id) == []
        assert fine.status == "failed"
        assert len(await _costs(async_db, fine.id)) == 1

    @pytest.mark.asyncio
    async def test_live_finished_and_other_runs_are_left_alone(self, async_db, ctx, caplog):
        live = await _image_run(async_db, ctx, idle=timedelta(seconds=5))
        finished = await _image_run(async_db, ctx, status="running")
        await TraceWriter(async_db, ctx).update_run_status(finished.id, "succeeded")
        finished = await async_db.get(Run, finished.id)
        finished.updated_at = utc_now() - timedelta(hours=1)
        async_db.add(finished)
        other = await _image_run(async_db, ctx, kind="chat")
        await async_db.commit()

        assert await _reap(async_db) == 0

        for run, status in ((live, "running"), (finished, "succeeded"), (other, "running")):
            await async_db.refresh(run)
            assert run.status == status
        # Not even tried: a finished run is no failed reap.
        assert "Could not reap" not in caplog.text

    @pytest.mark.asyncio
    async def test_a_short_orphan_window_never_undercuts_the_heartbeat(self, async_db, ctx):
        # Idle for less than three heartbeats (30s each): the job may still be alive.
        run = await _image_run(async_db, ctx, idle=timedelta(seconds=60))

        assert await reap_interrupted_image_runs(async_db, orphan_after_seconds=1, describe_route=_Describer()) == 0

        await async_db.refresh(run)
        assert run.status == "running"

    @pytest.mark.asyncio
    async def test_the_default_describer_asks_the_router_for_the_route(self, async_db, ctx):
        run = await _image_run(async_db, ctx)
        await _step(async_db, ctx, run.id, _NOTE)
        asked: list[tuple[Any, ...]] = []

        class _Router:
            async def describe_route(self, model_ref: str, ctx_: Any, capabilities: tuple[str, ...]) -> Any:
                asked.append((model_ref, ctx_.workspace_id, capabilities))
                return SimpleNamespace(pricing={"currency": "USD", "image": "0.05"}, target=None)

        container = get_container()
        original = container.get("llm_port")
        container.register_singleton("llm_port", _Router())
        try:
            await reap_interrupted_image_runs(async_db, orphan_after_seconds=600)
        finally:
            container.register_singleton("llm_port", original)

        assert asked == [("model:painter:gpt-image-1", ctx.workspace_id, ("image_generation",))]
        (charge,) = await _costs(async_db, run.id)
        assert Decimal(str(charge.amount)) == Decimal("0.10")

    @pytest.mark.asyncio
    async def test_a_sweep_that_fails_does_not_stop_the_loop(self, monkeypatch):
        sweeps: list[str] = []

        async def reap(_db: Any) -> int:
            sweeps.append("sweep")
            if len(sweeps) == 1:
                raise RuntimeError("database unavailable")
            return 0

        async def sleep(_seconds: float) -> None:
            if len(sweeps) >= 2:
                raise asyncio.CancelledError

        session = MagicMock(rollback=AsyncMock(), close=AsyncMock())
        monkeypatch.setattr(image_job, "reap_interrupted_image_runs", reap)
        monkeypatch.setattr(image_job.asyncio, "sleep", sleep)

        with pytest.raises(asyncio.CancelledError):
            await image_job.run_image_reaper_loop(lambda: session, interval_seconds=60)

        assert sweeps == ["sweep", "sweep"]
        assert session.close.await_count == 2


class TestTheHeartbeat:
    @pytest.mark.asyncio
    async def test_a_run_in_progress_is_kept_alive_beat_after_beat(self, async_db, ctx):
        run = await _image_run(async_db, ctx)
        seen = [run.updated_at.replace(tzinfo=None)]

        async with keep_image_run_alive(async_db.bind, run.id, interval_seconds=1.0):
            for _ in range(2):
                await asyncio.sleep(1.2)
                await async_db.refresh(run)
                seen.append(run.updated_at.replace(tzinfo=None))

        assert seen[0] < seen[1] < seen[2]
        assert await _reap(async_db) == 0

    @pytest.mark.asyncio
    async def test_a_finished_run_is_not_touched(self, async_db, ctx):
        run = await _image_run(async_db, ctx)
        await TraceWriter(async_db, ctx).update_run_status(run.id, "succeeded")
        await async_db.commit()
        await async_db.refresh(run)
        ended = run.updated_at

        async with keep_image_run_alive(async_db.bind, run.id, interval_seconds=1.0):
            await asyncio.sleep(1.3)

        await async_db.refresh(run)
        assert run.updated_at == ended


class _Spy:
    """Stands in for keep_image_run_alive: records the bind and whether the job ran inside."""

    def __init__(self) -> None:
        self.runs: list[str] = []
        self.binds: list[Any] = []
        self.active = False
        self.job_ran_inside: list[bool] = []

    @contextlib.asynccontextmanager
    async def __call__(self, bind: Any, run_id: str, **_kwargs: Any):
        self.runs.append(run_id)
        self.binds.append(bind)
        self.active = True
        try:
            yield
        finally:
            self.active = False

    def around(self, execute: Any) -> Any:
        async def run(*args: Any, **kwargs: Any) -> Any:
            self.job_ran_inside.append(self.active)
            return await execute(*args, **kwargs)

        return run


class TestEveryImageCallIsKeptAlive:
    @pytest.mark.asyncio
    async def test_a_synchronous_native_call(self, async_client, async_db, monkeypatch):
        from app.api.v1.images import router as native

        spy = _Spy()
        monkeypatch.setattr(native, "keep_image_run_alive", spy)
        monkeypatch.setattr(native, "execute_image_job", spy.around(native.execute_image_job))

        response = await async_client.post(
            "/api/v1/images/generations", json={"model": "model:test:seedream", "prompt": "a red dot"}
        )

        assert response.status_code == 201, response.text
        assert spy.runs == [response.json()["data"]["run_id"]]
        assert spy.binds == [async_db.bind]
        assert spy.job_ran_inside == [True]

    @pytest.mark.asyncio
    async def test_an_openai_compatible_call(self, async_client, async_db, monkeypatch):
        from app.api.openai import router as gateway

        spy = _Spy()
        monkeypatch.setattr(gateway, "keep_image_run_alive", spy)
        monkeypatch.setattr(gateway, "execute_image_job", spy.around(gateway.execute_image_job))

        response = await async_client.post(
            "/v1/images/generations", json={"model": "model:test:seedream", "prompt": "a red dot"}
        )

        assert response.status_code == 200, response.text
        assert spy.runs == [response.headers["x-soit-run-id"]]
        assert spy.binds == [async_db.bind]
        assert spy.job_ran_inside == [True]

    @pytest.mark.asyncio
    async def test_an_asynchronous_job(self, async_db, ctx, monkeypatch):
        from app.kernel.runtime.images.service import ImageJobRequest

        spy = _Spy()
        monkeypatch.setattr(image_job, "keep_image_run_alive", spy)
        monkeypatch.setattr(image_job, "execute_image_job", spy.around(image_job.execute_image_job))
        run = await TraceWriter(async_db, ctx).create_run("image")
        await async_db.commit()

        await image_job.run_image_job_detached(
            bind=async_db.bind,
            ctx=ctx,
            request=ImageJobRequest(kind="generate", model="model:test:m", prompt="hi", response_format="artifact"),
            run_id=run.id,
        )

        assert spy.runs == [run.id]
        assert spy.binds == [async_db.bind]
        assert spy.job_ran_inside == [True]
