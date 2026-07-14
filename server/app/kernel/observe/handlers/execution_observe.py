"""Subscribe to execution outbox facts: trace export, Prometheus, usage logs (Wave C)."""

from __future__ import annotations

import json
import logging
from datetime import UTC
from decimal import Decimal

from sqlmodel import Session

from app.kernel.observe.event_types import ObserveEventType
from app.kernel.observe.metrics import (
    active_runs,
    cost_total,
    run_count,
    run_duration,
    step_count,
    step_duration,
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


def handle_run_created_observe(db: Session, row: EventOutbox) -> None:
    """Mirror former TraceWriter.create_run observe (tracer, exporter, run counters)."""
    if row.event_type != RunEventType.CREATED:
        return
    if not try_claim_projection_slot(
        db, consumer_name="observe.run_created.side_effects", event_id=row.event_id
    ):
        return

    rid = _resolve_run_id(row)
    if not rid:
        return
    run = db.get(Run, rid)
    if run is None:
        return

    exporter = OpenTelemetryExporter()
    tracer.trace_run(run, {"event": "created"})
    exporter.export_run(run)
    run_count.labels(mode=run.mode, status="queued", tenant_id=run.tenant_id).inc()
    active_runs.labels(mode=run.mode, tenant_id=run.tenant_id).inc()


def handle_task_lifecycle_observe(db: Session, row: EventOutbox) -> None:
    """Structured usage log hook; extend with usage_events table when needed."""
    consumer = f"observe.task.{row.event_type}"
    if not try_claim_projection_slot(db, consumer_name=consumer, event_id=row.event_id):
        return
    payload = row.payload_json or {}
    logger.info(
        "usage.task %s %s",
        row.event_type,
        json.dumps(payload, ensure_ascii=False, default=str)[:8192],
    )


def handle_workflow_node_observe(db: Session, row: EventOutbox) -> None:
    """Audit-style log for workflow node facts (DB counters stay on workflow handler)."""
    consumer = f"observe.workflow.{row.event_type}"
    if not try_claim_projection_slot(db, consumer_name=consumer, event_id=row.event_id):
        return
    payload = row.payload_json or {}
    logger.info(
        "usage.workflow_node %s %s",
        row.event_type,
        json.dumps(payload, ensure_ascii=False, default=str)[:8192],
    )


def handle_run_status_updated_observe(db: Session, row: EventOutbox) -> None:
    """Mirror former TraceWriter.update_run_status observe (tracer, exporter, run metrics)."""
    if row.event_type != ObserveEventType.RUN_STATUS_UPDATED:
        return
    if not try_claim_projection_slot(
        db, consumer_name="observe.run_status.side_effects", event_id=row.event_id
    ):
        return
    payload = row.payload_json or {}
    rid = payload.get("run_id") or row.run_id
    if not rid:
        return
    run = db.get(Run, rid)
    if run is None:
        return

    old_status = payload.get("old_status")
    new_status = payload.get("new_status")
    mode = payload.get("mode") or run.mode
    tenant_id = payload.get("tenant_id") or run.tenant_id

    exporter = OpenTelemetryExporter()
    tracer.trace_run(run, {"event": "status"})
    exporter.export_run(run)

    if run.status in ("succeeded", "failed", "canceled"):
        if run.started_at and run.ended_at:
            started_at = run.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=UTC)
            duration_seconds = (run.ended_at - started_at).total_seconds()
            run_duration.labels(mode=run.mode, tenant_id=tenant_id).observe(duration_seconds)
        active_runs.labels(mode=run.mode, tenant_id=tenant_id).dec()

    if old_status is not None and new_status is not None and old_status != new_status:
        run_count.labels(mode=mode, status=new_status, tenant_id=tenant_id).inc()


def handle_step_created_observe(db: Session, row: EventOutbox) -> None:
    """Mirror former TraceWriter.create_step observe (tracer, exporter, step counter)."""
    if row.event_type != ObserveEventType.STEP_CREATED:
        return
    if not try_claim_projection_slot(
        db, consumer_name="observe.step_created.side_effects", event_id=row.event_id
    ):
        return
    payload = row.payload_json or {}
    sid = payload.get("step_row_id")
    if not sid:
        return
    step = db.get(RunStep, sid)
    if step is None:
        return

    tenant_id = payload.get("tenant_id") or step.tenant_id
    exporter = OpenTelemetryExporter()
    tracer.trace_step(step, {"event": "created"})
    exporter.export_step(step)
    step_count.labels(step_type=step.step_type, status="queued", tenant_id=tenant_id).inc()


def handle_step_status_updated_observe(db: Session, row: EventOutbox) -> None:
    """Mirror former TraceWriter.update_step_status observe."""
    if row.event_type != ObserveEventType.STEP_STATUS_UPDATED:
        return
    if not try_claim_projection_slot(
        db, consumer_name="observe.step_status.side_effects", event_id=row.event_id
    ):
        return
    payload = row.payload_json or {}
    sid = payload.get("step_row_id")
    if not sid:
        return
    step = db.get(RunStep, sid)
    if step is None:
        return

    old_status = payload.get("old_status")
    new_status = payload.get("new_status")
    tenant_id = payload.get("tenant_id") or step.tenant_id

    exporter = OpenTelemetryExporter()
    tracer.trace_step(step, {"event": "status"})
    exporter.export_step(step)

    if step.status in ("succeeded", "failed", "skipped", "canceled"):
        if step.started_at and step.ended_at:
            started_at = step.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=UTC)
            duration_seconds = (step.ended_at - started_at).total_seconds()
            step_duration.labels(step_type=step.step_type, tenant_id=tenant_id).observe(
                duration_seconds
            )

    if old_status is not None and new_status is not None and old_status != new_status:
        step_count.labels(step_type=step.step_type, status=new_status, tenant_id=tenant_id).inc()


def handle_cost_recorded_observe(db: Session, row: EventOutbox) -> None:
    """Apply token/cost Prometheus counters idempotently per cost entry."""
    if not try_claim_projection_slot(
        db, consumer_name="observe.cost.metrics", event_id=row.event_id
    ):
        return
    payload = row.payload_json or {}
    tenant_id = payload.get("tenant_id") or row.tenant_id
    if not tenant_id:
        return

    prompt_tokens = payload.get("prompt_tokens")
    if prompt_tokens:
        tokens_total.labels(type="prompt", tenant_id=tenant_id).inc(int(prompt_tokens))
    completion_tokens = payload.get("completion_tokens")
    if completion_tokens:
        tokens_total.labels(type="completion", tenant_id=tenant_id).inc(int(completion_tokens))

    unit = payload.get("unit") or ""
    quantity = payload.get("quantity")
    if unit in ("embeddings", "embedding") and quantity is not None:
        try:
            tokens_total.labels(type="embedding", tenant_id=tenant_id).inc(float(Decimal(str(quantity))))
        except Exception:
            pass

    amount = payload.get("amount")
    if amount is not None:
        try:
            amt = float(Decimal(str(amount)))
            if amt > 0:
                cost_total.labels(resource_type=str(unit or "unknown"), tenant_id=tenant_id).inc(amt)
        except Exception:
            pass
