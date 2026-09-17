"""In-process observation of run and step transitions.

Step lifecycle and intermediate run transitions are observed where they
happen: trace span, OTel export and Prometheus counters, no outbox row. Only
terminal run transitions stay on the outbox, because their consumers
(failure notifications) need exactly-once delivery.
"""

from __future__ import annotations

from datetime import UTC

from app.kernel.observe.metrics import (
    active_runs,
    run_count,
    run_duration,
    step_count,
    step_duration,
)
from app.kernel.observe.tracing import tracer
from app.kernel.runtime.db.models.runs import Run, RunStep
from app.kernel.runtime.runs.exporter import OpenTelemetryExporter

TERMINAL_RUN_STATUSES = frozenset({"succeeded", "failed", "canceled"})
TERMINAL_STEP_STATUSES = frozenset({"succeeded", "failed", "skipped", "canceled"})


def _seconds_between(started_at, ended_at) -> float:
    # Rows refreshed from the database are naive UTC; values set in this
    # process are aware. Normalise both before subtracting.
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    if ended_at.tzinfo is None:
        ended_at = ended_at.replace(tzinfo=UTC)
    return (ended_at - started_at).total_seconds()


def observe_run_status_transition(
    run: Run,
    *,
    old_status: str | None,
    new_status: str | None,
    mode: str | None = None,
    tenant_id: str | None = None,
) -> None:
    """Trace, export and count one run status change."""
    resolved_mode = mode or run.mode
    tenant = tenant_id or run.tenant_id
    exporter = OpenTelemetryExporter()
    tracer.trace_run(run, {"event": "status"})
    exporter.export_run(run)

    if run.status in TERMINAL_RUN_STATUSES:
        if run.started_at and run.ended_at:
            run_duration.labels(mode=run.mode, tenant_id=tenant).observe(
                _seconds_between(run.started_at, run.ended_at)
            )
        active_runs.labels(mode=run.mode, tenant_id=tenant).dec()

    if old_status is not None and new_status is not None and old_status != new_status:
        run_count.labels(mode=resolved_mode, status=new_status, tenant_id=tenant).inc()


def observe_step_created(step: RunStep, *, tenant_id: str | None = None) -> None:
    """Trace, export and count a newly created step."""
    tenant = tenant_id or step.tenant_id
    exporter = OpenTelemetryExporter()
    tracer.trace_step(step, {"event": "created"})
    exporter.export_step(step)
    step_count.labels(step_type=step.step_type, status="queued", tenant_id=tenant).inc()


def observe_step_status_transition(
    step: RunStep,
    *,
    old_status: str | None,
    new_status: str | None,
    tenant_id: str | None = None,
) -> None:
    """Trace, export and count one step status change."""
    tenant = tenant_id or step.tenant_id
    exporter = OpenTelemetryExporter()
    tracer.trace_step(step, {"event": "status"})
    exporter.export_step(step)

    if step.status in TERMINAL_STEP_STATUSES and step.started_at and step.ended_at:
        step_duration.labels(step_type=step.step_type, tenant_id=tenant).observe(
            _seconds_between(step.started_at, step.ended_at)
        )

    if old_status is not None and new_status is not None and old_status != new_status:
        step_count.labels(step_type=step.step_type, status=new_status, tenant_id=tenant).inc()
