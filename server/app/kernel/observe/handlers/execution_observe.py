"""Subscribe to execution outbox facts: trace export, Prometheus, usage logs (Wave C)."""

from __future__ import annotations

import json
import logging
from decimal import Decimal

from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.observe.event_types import ObserveEventType
from app.kernel.observe.execution_metrics import (
    observe_run_status_transition,
    observe_step_created,
    observe_step_status_transition,
)
from app.kernel.observe.metrics import (
    active_runs,
    cost_total,
    run_count,
    tokens_total,
)
from app.kernel.observe.projection_repo import try_claim_projection_slot
from app.kernel.observe.tracing import tracer
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.db.models.runs import Run, RunStep
from app.kernel.runtime.runs.events import RunEventType
from app.kernel.runtime.runs.exporter import OpenTelemetryExporter

logger = logging.getLogger(__name__)


def _resolve_run_id(row: EventOutbox) -> str | None:
    if row.run_id:
        return row.run_id
    payload = row.payload_json or {}
    return payload.get("run_id") or row.subject_id


async def handle_run_created_observe(db: AsyncSession, row: EventOutbox) -> None:
    """Mirror former TraceWriter.create_run observe (tracer, exporter, run counters)."""
    if row.event_type != RunEventType.CREATED:
        return
    if not await try_claim_projection_slot(
        db, consumer_name="observe.run_created.side_effects", event_id=row.event_id
    ):
        return

    rid = _resolve_run_id(row)
    if not rid:
        return
    run = await db.get(Run, rid)
    if run is None:
        return

    exporter = OpenTelemetryExporter()
    tracer.trace_run(run, {"event": "created"})
    exporter.export_run(run)
    run_count.labels(mode=run.mode, status="queued", tenant_id=run.tenant_id).inc()
    active_runs.labels(mode=run.mode, tenant_id=run.tenant_id).inc()


async def handle_task_lifecycle_observe(db: AsyncSession, row: EventOutbox) -> None:
    """Structured usage log hook; extend with usage_events table when needed."""
    consumer = f"observe.task.{row.event_type}"
    if not await try_claim_projection_slot(db, consumer_name=consumer, event_id=row.event_id):
        return
    payload = row.payload_json or {}
    logger.info(
        "usage.task %s %s",
        row.event_type,
        json.dumps(payload, ensure_ascii=False, default=str)[:8192],
    )


async def handle_workflow_node_observe(db: AsyncSession, row: EventOutbox) -> None:
    """Audit-style log for workflow node facts (DB counters stay on workflow handler)."""
    consumer = f"observe.workflow.{row.event_type}"
    if not await try_claim_projection_slot(db, consumer_name=consumer, event_id=row.event_id):
        return
    payload = row.payload_json or {}
    logger.info(
        "usage.workflow_node %s %s",
        row.event_type,
        json.dumps(payload, ensure_ascii=False, default=str)[:8192],
    )


async def handle_run_status_updated_observe(db: AsyncSession, row: EventOutbox) -> None:
    """Mirror former TraceWriter.update_run_status observe (tracer, exporter, run metrics)."""
    if row.event_type != ObserveEventType.RUN_STATUS_UPDATED:
        return
    if not await try_claim_projection_slot(
        db, consumer_name="observe.run_status.side_effects", event_id=row.event_id
    ):
        return
    payload = row.payload_json or {}
    rid = payload.get("run_id") or row.run_id
    if not rid:
        return
    run = await db.get(Run, rid)
    if run is None:
        return

    observe_run_status_transition(
        run,
        old_status=payload.get("old_status"),
        new_status=payload.get("new_status"),
        mode=payload.get("mode") or run.mode,
        tenant_id=payload.get("tenant_id") or run.tenant_id,
    )


async def handle_step_created_observe(db: AsyncSession, row: EventOutbox) -> None:
    """Observe a step.created row still on the outbox (the writer no longer emits them)."""
    if row.event_type != ObserveEventType.STEP_CREATED:
        return
    if not await try_claim_projection_slot(
        db, consumer_name="observe.step_created.side_effects", event_id=row.event_id
    ):
        return
    payload = row.payload_json or {}
    sid = payload.get("step_row_id")
    if not sid:
        return
    step = await db.get(RunStep, sid)
    if step is None:
        return

    observe_step_created(step, tenant_id=payload.get("tenant_id") or step.tenant_id)


async def handle_step_status_updated_observe(db: AsyncSession, row: EventOutbox) -> None:
    """Observe a step.status.updated row still on the outbox (no longer emitted)."""
    if row.event_type != ObserveEventType.STEP_STATUS_UPDATED:
        return
    if not await try_claim_projection_slot(
        db, consumer_name="observe.step_status.side_effects", event_id=row.event_id
    ):
        return
    payload = row.payload_json or {}
    sid = payload.get("step_row_id")
    if not sid:
        return
    step = await db.get(RunStep, sid)
    if step is None:
        return

    observe_step_status_transition(
        step,
        old_status=payload.get("old_status"),
        new_status=payload.get("new_status"),
        tenant_id=payload.get("tenant_id") or step.tenant_id,
    )


async def handle_cost_recorded_observe(db: AsyncSession, row: EventOutbox) -> None:
    """Apply token/cost Prometheus counters idempotently per cost entry."""
    if not await try_claim_projection_slot(
        db, consumer_name="observe.cost.metrics", event_id=row.event_id
    ):
        return
    payload = row.payload_json or {}
    tenant_id = payload.get("tenant_id") or row.tenant_id
    if not tenant_id:
        return

    # entry_type no longer exists on cost rows; pre-removal events may still
    # carry it, and legacy charge events must not count as usage.
    records_usage = payload.get("entry_type") in (None, "usage")
    # Events published before the billing_basis rename still carry unit/quantity.
    billing_basis = payload.get("billing_basis") or payload.get("unit") or ""
    if records_usage:
        prompt_tokens = payload.get("prompt_tokens")
        if prompt_tokens:
            tokens_total.labels(type="prompt", tenant_id=tenant_id).inc(int(prompt_tokens))
        completion_tokens = payload.get("completion_tokens")
        if completion_tokens:
            tokens_total.labels(type="completion", tenant_id=tenant_id).inc(int(completion_tokens))

        embedding_count = payload.get("embedding_count")
        if embedding_count is None and billing_basis in ("embeddings", "embedding"):
            embedding_count = payload.get("billed_quantity", payload.get("quantity"))
        if embedding_count is not None:
            try:
                tokens_total.labels(type="embedding", tenant_id=tenant_id).inc(float(Decimal(str(embedding_count))))
            except Exception:
                pass

    amount = payload.get("amount")
    if amount is not None:
        try:
            amt = float(Decimal(str(amount)))
            if amt > 0:
                cost_total.labels(resource_type=str(billing_basis or "unknown"), tenant_id=tenant_id).inc(amt)
        except Exception:
            pass
