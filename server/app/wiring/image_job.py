""" image_job

Detached execution for asynchronous image jobs.

Image providers routinely spend minutes on a batch, and four 2048px images come
back as 10-16 MB of base64. Holding an HTTP request open across both is what
makes large image work fail at the gateway rather than at the model, so the
asynchronous path hands back a run id immediately and finishes the work here.

This follows the same shape as the workflow redrive worker: an asyncio task on
its own session, a strong reference held until it finishes so the loop cannot
garbage-collect it mid-flight, and the run closed on every exit path. There is
no Celery broker in this deployment; the dependency is declared but nothing is
wired to it, and adding one for this would be a second execution model to
operate for no gain.

A job in progress, and a synchronous image call too, marks its run alive every
``image_job_heartbeat_seconds``. A run no process has marked alive for
``image_job_orphan_after_seconds`` was lost with the process that ran it: the
reaper here fails it, and charges the provider call it left in flight, which
the provider does not cancel and may still bill.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator, Callable
from datetime import timedelta
from typing import Any, NamedTuple

from sqlalchemy import select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import KernelError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.policy import unconfirmed_image_charge
from app.kernel.runtime.db.models.runs import Run, RunCostEntry, RunStep
from app.kernel.runtime.images.service import (
    ImageJobRequest,
    execute_image_job,
    resolve_response_format,
)
from app.kernel.runtime.runs.writer import TraceWriter
from app.settings.settings import settings

logger = logging.getLogger(__name__)

# Tasks are kept referenced until they finish: asyncio holds only a weak
# reference, so a task that nothing else points at can be collected while it is
# still running and the run would never leave "running".
_image_tasks: set[asyncio.Task] = set()

INTERRUPTED_ERROR_CODE = "IMAGE_JOB_INTERRUPTED"
INTERRUPTED_ERROR_MESSAGE = (
    "The image job stopped with the process that ran it and cannot be "
    "resumed; submit it again if needed"
)
_OPEN_RUN_STATUSES = ("queued", "running")
_REAPER_ACTOR = "system:image-job-reaper"


@contextlib.asynccontextmanager
async def keep_image_run_alive(
    bind: Any,
    run_id: str,
    *,
    interval_seconds: float | None = None,
) -> AsyncIterator[None]:
    """Mark ``run_id`` alive while the block runs, so the reaper leaves it alone.

    Each beat is its own short transaction on its own session: the job's
    session may be mid-transaction, and a beat must not commit its work.
    """
    interval = max(1.0, float(interval_seconds or settings.image_job_heartbeat_seconds))

    async def beat() -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                async with AsyncSession(bind=bind) as db:
                    await db.execute(
                        update(Run)
                        .where(Run.id == run_id, Run.status.in_(_OPEN_RUN_STATUSES))
                        .values(updated_at=utc_now())
                    )
                    await db.commit()
            except Exception:
                logger.warning("Image run heartbeat failed", extra={"run_id": run_id}, exc_info=True)

    task = asyncio.create_task(beat())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def run_image_job_detached(
    *,
    bind: Any,
    ctx: RequestContext,
    request: ImageJobRequest,
    run_id: str,
) -> None:
    """Execute one image job on its own session and close its run."""
    from app.wiring import get_container

    async with (
        AsyncSession(bind=bind, expire_on_commit=False) as db,
        keep_image_run_alive(bind, run_id),
    ):
        container = get_container()
        trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())
        try:
            # Its results reach the caller only through the run.
            resolve_response_format(request.response_format, detached=True)
            await trace_writer.update_run_status(run_id, "running")
            await db.commit()

            outcome = await execute_image_job(
                request,
                run_id=run_id,
                ctx=ctx,
                llm_port=container.get_llm_port(ctx=ctx, trace_writer=trace_writer),
                trace_writer=trace_writer,
                storage_port=container.get_storage_port(ctx=ctx),
                content_safety=container.get_content_safety_port(ctx, trace_writer),
            )
            summary = f"images={len(outcome.results)}"
            if outcome.safety:
                summary = f"{summary}, safety_findings={len(outcome.safety)}"
            await trace_writer.update_run_status(
                run_id,
                "succeeded",
                output_summary=summary,
            )
            await db.commit()
        except Exception as exc:
            logger.exception("Async image job failed", extra={"run_id": run_id})
            try:
                await trace_writer.update_run_status(
                    run_id,
                    "failed",
                    # The run is all an async caller sees: it carries the
                    # failure's own code when there is one.
                    error_code=exc.code if isinstance(exc, KernelError) else "IMAGE_ERROR",
                    error_message=str(exc)[:2000],
                )
                await db.commit()
            except Exception:
                # The run is the caller's only signal. Losing the failure
                # transition strands it as "running" forever, so say so loudly
                # rather than letting it disappear with the task.
                logger.exception(
                    "Async image job could not record its failure",
                    extra={"run_id": run_id},
                )


def start_detached_image_job(
    *,
    bind: Any,
    ctx: RequestContext,
    request: ImageJobRequest,
    run_id: str,
) -> asyncio.Task:
    """Schedule an image job and return immediately."""
    task = asyncio.create_task(
        run_image_job_detached(bind=bind, ctx=ctx, request=request, run_id=run_id)
    )
    _image_tasks.add(task)
    task.add_done_callback(_image_tasks.discard)
    return task


RouteDescriber = Callable[[RequestContext, str, str], Any]

_TERMINAL_STEP_STATUSES = ("succeeded", "failed", "skipped", "canceled", "expired")


async def _describe_route(ctx: RequestContext, model_ref: str, capability: str) -> Any:
    """The route a call to ``model_ref`` takes now, for its pricing; None if there is none.

    Any failure to describe it, a provider since disabled or a configuration
    that no longer reads, leaves the charge unpriced rather than the run open.
    """
    from app.wiring import get_container

    router = get_container().get("llm_port")
    describe = getattr(router, "describe_route", None)
    if describe is None:
        return None
    try:
        return await describe(model_ref, ctx, (capability,))
    except Exception:
        logger.warning("Could not price an interrupted image call", extra={"model_ref": model_ref}, exc_info=True)
        return None


def _orphan_after_seconds(configured: float | None) -> float:
    # Never within a few beats of the heartbeat, or a live job would be reaped.
    floor = 3 * max(1.0, float(settings.image_job_heartbeat_seconds))
    return max(floor, float(configured or settings.image_job_orphan_after_seconds))


async def reap_interrupted_image_runs(
    db: AsyncSession,
    *,
    orphan_after_seconds: float | None = None,
    describe_route: RouteDescriber = _describe_route,
    limit: int = 50,
) -> int:
    """Fail image runs no process has marked alive; returns how many were reaped.

    A model step still running was a call in flight: the provider was asked
    for the images and does not cancel the work, so the step is charged the
    count it asked for, flagged as estimated, at the price its route has now.
    Runs are locked with ``SKIP LOCKED`` so sweeps on several replicas take
    distinct runs, and each is reaped in its own savepoint, so one that cannot
    be reaped is skipped rather than holding back the rest.
    """
    cutoff = utc_now() - timedelta(seconds=_orphan_after_seconds(orphan_after_seconds))
    runs = (
        (
            await db.execute(
                select(Run)
                .where(
                    Run.kind == "image",
                    Run.status.in_(_OPEN_RUN_STATUSES),
                    Run.updated_at < cutoff,
                )
                .order_by(Run.updated_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    if not runs:
        await db.rollback()
        return 0
    # Plain values: a savepoint rolled back expires the loaded rows.
    lost = [_LostRun(run.id, run.tenant_id, run.workspace_id) for run in runs]
    reaped = 0
    for run in lost:
        try:
            async with db.begin_nested():
                if await _reap_run(db, run, describe_route):
                    reaped += 1
        except Exception:
            logger.exception("Could not reap an interrupted image run", extra={"run_id": run.id})
    await db.commit()
    return reaped


class _LostRun(NamedTuple):
    id: str
    tenant_id: str
    workspace_id: str


async def _reap_run(db: AsyncSession, run: _LostRun, describe_route: RouteDescriber) -> bool:
    """Close one lost run and its open steps; False if a live process still holds a step."""
    scope = (RunStep.tenant_id == run.tenant_id, RunStep.workspace_id == run.workspace_id)
    open_steps = RunStep.run_id == run.id, RunStep.status.not_in(_TERMINAL_STEP_STATUSES)
    open_count = len((await db.execute(select(RunStep.id).where(*scope, *open_steps))).all())
    steps = (
        (await db.execute(select(RunStep).where(*scope, *open_steps).with_for_update(skip_locked=True)))
        .scalars()
        .all()
    )
    if len(steps) != open_count:
        # A process is writing one of them: the job is alive after all.
        return False
    ctx = RequestContext(
        tenant_id=run.tenant_id,
        workspace_id=run.workspace_id,
        user_id=_REAPER_ACTOR,
    )
    writer = TraceWriter(db, ctx)
    for step in steps:
        await _close_step(db, writer, run, step, describe_route)
    await writer.update_run_status(
        run.id,
        "failed",
        error_code=INTERRUPTED_ERROR_CODE,
        error_message=INTERRUPTED_ERROR_MESSAGE,
    )
    logger.warning("Failed interrupted image run", extra={"run_id": run.id})
    return True


async def _close_step(
    db: AsyncSession,
    writer: TraceWriter,
    run: _LostRun,
    step: RunStep,
    describe_route: RouteDescriber,
) -> None:
    """Fail a step the lost process left open, charging a model call it left in flight."""
    metrics = step.metrics_json or {}
    images = metrics.get("requested_images")
    model_ref = metrics.get("model_ref")
    charge = (
        step.step_type == "llm"
        and step.status == "running"
        and isinstance(images, int)
        and not isinstance(images, bool)
        and images > 0
        and isinstance(model_ref, str)
        and not await _already_charged(db, run, step)
    )
    await writer.update_step_status(
        step.id,
        "failed",
        metrics={"usage_estimated": True} if charge else None,
        error_code=INTERRUPTED_ERROR_CODE,
        error_message=INTERRUPTED_ERROR_MESSAGE,
    )
    if not charge:
        return
    edit = metrics.get("image_edit") is True
    route = await describe_route(writer.ctx, model_ref, "image_edit" if edit else "image_generation")
    target = getattr(route, "target", None)
    pricing, identity = unconfirmed_image_charge(
        getattr(route, "pricing", None) or {},
        requested_model=metrics.get("model") if isinstance(metrics.get("model"), str) else model_ref,
        target=target,
        images=images,
        unpriced_reason=None if route is not None else "route_not_resolved",
    )
    if target is None:
        # The route is gone: the step still names who served the call.
        identity.update(
            model_ref=model_ref,
            **{key: metrics.get(key) for key in ("provider_id", "provider_slug", "provider_kind")},
            provider=metrics.get("provider_kind"),
        )
    await writer.record_cost(
        run_id=run.id,
        step_id=step.id,
        billing_basis="images",
        billed_quantity=images,
        currency=pricing.currency,
        amount=pricing.amount,
        pricing_snapshot_json=pricing.snapshot,
        **identity,
        source_port="llm",
        operation="edit_image" if edit else "generate_image",
        request_count=images,
    )


async def _already_charged(db: AsyncSession, run: _LostRun, step: RunStep) -> bool:
    return (
        await db.execute(
            select(RunCostEntry.id)
            .where(
                RunCostEntry.tenant_id == run.tenant_id,
                RunCostEntry.workspace_id == run.workspace_id,
                RunCostEntry.step_id == step.id,
            )
            .limit(1)
        )
    ).first() is not None


async def run_image_reaper_loop(
    db_factory: Callable[[], AsyncSession],
    *,
    interval_seconds: float,
) -> None:
    """Periodically fail image runs lost with the process that ran them."""
    interval = max(5.0, float(interval_seconds or 0))
    while True:
        db = db_factory()
        try:
            await reap_interrupted_image_runs(db)
        except Exception:
            logger.exception("Interrupted image run sweep failed")
            with contextlib.suppress(Exception):
                await db.rollback()
        finally:
            await db.close()
        await asyncio.sleep(interval)
