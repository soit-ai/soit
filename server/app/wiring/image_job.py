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
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.images.service import ImageJobRequest, execute_image_job
from app.kernel.runtime.runs.writer import TraceWriter

logger = logging.getLogger(__name__)

# Tasks are kept referenced until they finish: asyncio holds only a weak
# reference, so a task that nothing else points at can be collected while it is
# still running and the run would never leave "running".
_image_tasks: set[asyncio.Task] = set()


async def run_image_job_detached(
    *,
    bind: Any,
    ctx: RequestContext,
    request: ImageJobRequest,
    run_id: str,
) -> None:
    """Execute one image job on its own session and close its run."""
    from app.wiring import get_container

    async with AsyncSession(bind=bind, expire_on_commit=False) as db:
        container = get_container()
        trace_writer = TraceWriter(db, ctx, event_bus=container.get_event_bus())
        try:
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
                    error_code="IMAGE_ERROR",
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
