"""otlp

A trace as an OTLP/JSON ``ExportTraceServiceRequest``.

SOIT has no span store: a trace is the set of runs sharing a ``trace_id``,
and their steps are the spans. This module renders that set in the shape an
OpenTelemetry collector, Jaeger or Tempo accepts over OTLP/HTTP JSON, so a
trace can be handed to the tooling a team already uses. The document is the
contract ``kernel/specs/v1/otlp_trace_spec.schema.json``.

The export carries identifiers, kinds, statuses, timings and numeric metrics
only: no summaries, error text or tool content, so it holds nothing a
content-free (``metadata_only``) workspace withholds and needs no capture
lookup. Everything else the ledger records is in the run evidence bundle.

Identifiers follow the OTLP wire format: a trace id is 16 bytes and a span
id 8 bytes, written as lowercase hex, and 64-bit integers (timestamps in
nanoseconds, ``intValue``) are JSON strings as the protobuf JSON mapping
requires. Span ids are derived from record ids with a fixed-length BLAKE2b, so
the same run or step always gets the same span id and an export is
reproducible.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import NotFoundError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run, RunStep

OTLP_TRACE_SPEC = "otlp_trace_spec"
SCOPE_NAME = "soit"
SERVICE_NAME = "soit"

# OTLP enums, as the protobuf JSON mapping writes them (numbers).
SPAN_KIND_INTERNAL = 1
SPAN_KIND_SERVER = 2
SPAN_KIND_CLIENT = 3
STATUS_UNSET = 0
STATUS_OK = 1
STATUS_ERROR = 2

# Step types that call out of the runtime: a model, a tool, a store.
_CLIENT_STEP_HEADS = frozenset(
    {"llm", "model", "tool", "retrieval", "rerank", "embedding", "http"}
)
_HEX_TRACE_ID = re.compile(r"^[0-9a-fA-F]{32}$")
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def trace_id_hex(trace_id: str) -> str:
    """The OTLP trace id: 16 bytes as lowercase hex.

    A stored trace id that already is 32 hex characters (a W3C trace id) is
    used as is. Any other shape (a ULID, a prefixed id) is hashed to 16 bytes
    with BLAKE2b, so the same SOIT trace always maps to the same OTLP trace;
    the original id travels in the ``soit.trace.id`` resource attribute.
    """
    if _HEX_TRACE_ID.match(trace_id):
        return trace_id.lower()
    return hashlib.blake2b(trace_id.encode("utf-8"), digest_size=16).hexdigest()


def span_id_hex(record_id: str) -> str:
    """The OTLP span id of a run or step record: 8 bytes of BLAKE2b, as hex."""
    return hashlib.blake2b(record_id.encode("utf-8"), digest_size=8).hexdigest()


def unix_nano(value: datetime) -> str:
    """A timestamp as nanoseconds since the epoch, as the JSON string OTLP uses for fixed64."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    delta = value - _EPOCH
    seconds = delta.days * 86400 + delta.seconds
    return str(seconds * 1_000_000_000 + delta.microseconds * 1_000)


def _string(key: str, value: str | None) -> dict[str, Any] | None:
    if value is None or value == "":
        return None
    return {"key": key, "value": {"stringValue": value}}


def _int(key: str, value: int) -> dict[str, Any]:
    return {"key": key, "value": {"intValue": str(value)}}


def _bool(key: str, value: bool) -> dict[str, Any]:
    return {"key": key, "value": {"boolValue": value}}


def _attributes(*items: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [item for item in items if item is not None]


def _metric_attributes(metrics: Any) -> list[dict[str, Any]]:
    """The numeric top-level metrics of a step, as ``soit.step.metric.<name>``.

    Strings, booleans and nested objects are left out: they can carry
    identifiers or content (a tool call, a model ref), and the export is
    numbers and enumerations only.
    """
    if not isinstance(metrics, dict):
        return []
    attributes: list[dict[str, Any]] = []
    for key in sorted(metrics):
        value = metrics[key]
        if isinstance(value, bool) or not isinstance(value, int | float):
            continue
        name = f"soit.step.metric.{key}"
        if isinstance(value, int):
            attributes.append(_int(name, value))
        else:
            attributes.append({"key": name, "value": {"doubleValue": value}})
    return attributes


def _status(status: str, error_code: str | None) -> dict[str, Any]:
    if status == "succeeded":
        return {"code": STATUS_OK}
    if status == "failed":
        result: dict[str, Any] = {"code": STATUS_ERROR}
        if error_code:
            result["message"] = error_code
        return result
    return {"code": STATUS_UNSET}


def _span(
    *,
    trace_hex: str,
    span_hex: str,
    parent_hex: str | None,
    name: str,
    kind: int,
    started_at: datetime,
    ended_at: datetime | None,
    status: dict[str, Any],
    attributes: list[dict[str, Any]],
) -> dict[str, Any]:
    span: dict[str, Any] = {
        "traceId": trace_hex,
        "spanId": span_hex,
        "name": name,
        "kind": kind,
        "startTimeUnixNano": unix_nano(started_at),
        # A span still open ends where it started: OTLP has no open-ended span.
        "endTimeUnixNano": unix_nano(ended_at or started_at),
        "attributes": attributes,
        "status": status,
    }
    if parent_hex is not None:
        span["parentSpanId"] = parent_hex
    return span


def run_span(run: Run, trace_hex: str, run_span_ids: dict[str, str]) -> dict[str, Any]:
    """One run as a span; its parent is the parent run's span when that run is in the trace."""
    parent_hex = run_span_ids.get(run.parent_run_id) if run.parent_run_id else None
    return _span(
        trace_hex=trace_hex,
        span_hex=run_span_ids[run.id],
        parent_hex=parent_hex,
        name=f"run {run.kind or run.mode}",
        kind=SPAN_KIND_INTERNAL if parent_hex is not None else SPAN_KIND_SERVER,
        started_at=run.started_at,
        ended_at=run.ended_at,
        status=_status(run.status, run.error_code),
        attributes=_attributes(
            _string("soit.run.id", run.id),
            _string("soit.run.mode", run.mode),
            _string("soit.run.kind", run.kind),
            _string("soit.run.status", run.status),
            _string("soit.run.subject_kind", run.subject_kind),
            _string("soit.run.subject_id", run.subject_id),
            _string("soit.run.subject_version_id", run.subject_version_id),
            _string("soit.run.parent_run_id", run.parent_run_id),
            _string("soit.run.source_run_id", run.source_run_id),
            _int("soit.run.attempt_no", run.attempt_no),
            _string("soit.run.source", run.source),
            _bool("soit.run.sandbox", bool(run.sandbox)),
            _string("soit.run.error_code", run.error_code),
            _string("soit.run.error_step_id", run.error_step_id),
        ),
    )


def step_span(
    step: RunStep, trace_hex: str, run_span_ids: dict[str, str]
) -> dict[str, Any]:
    """One step as a span under its run's span."""
    head = step.step_type.split(".", 1)[0].split("_", 1)[0].lower()
    return _span(
        trace_hex=trace_hex,
        span_hex=span_id_hex(step.id),
        parent_hex=run_span_ids.get(step.run_id),
        name=step.step_type,
        kind=SPAN_KIND_CLIENT if head in _CLIENT_STEP_HEADS else SPAN_KIND_INTERNAL,
        started_at=step.started_at,
        ended_at=step.ended_at,
        status=_status(step.status, step.error_code),
        attributes=_attributes(
            _string("soit.run.id", step.run_id),
            _string("soit.step.id", step.id),
            _string("soit.step.step_id", step.step_id),
            _string("soit.step.type", step.step_type),
            _string("soit.step.node_id", step.node_id),
            _string("soit.step.status", step.status),
            _string("soit.step.error_code", step.error_code),
            *_metric_attributes(step.metrics_json),
        ),
    )


def build_trace_export(
    trace_id: str,
    runs: Iterable[Run],
    steps: Iterable[RunStep],
    *,
    tenant_id: str,
    workspace_id: str,
) -> dict[str, Any]:
    """The trace as an ``ExportTraceServiceRequest`` document.

    Runs come first, oldest first, then steps in the same order, so a reader
    meets every parent before its children. The result depends on the records
    alone: the same trace always renders the same document.
    """
    trace_hex = trace_id_hex(trace_id)
    ordered_runs = sorted(runs, key=lambda run: (run.started_at, run.id))
    ordered_steps = sorted(steps, key=lambda step: (step.started_at, step.id))
    run_span_ids = {run.id: span_id_hex(run.id) for run in ordered_runs}
    spans = [run_span(run, trace_hex, run_span_ids) for run in ordered_runs]
    spans.extend(step_span(step, trace_hex, run_span_ids) for step in ordered_steps)
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": _attributes(
                        _string("service.name", SERVICE_NAME),
                        _string("soit.tenant.id", tenant_id),
                        _string("soit.workspace.id", workspace_id),
                        _string("soit.trace.id", trace_id),
                    )
                },
                "scopeSpans": [{"scope": {"name": SCOPE_NAME}, "spans": spans}],
            }
        ]
    }


async def load_trace(
    session: AsyncSession, ctx: RequestContext, trace_id: str
) -> tuple[list[Run], list[RunStep]]:
    """Every run and step of ``trace_id`` in ``ctx``'s workspace; not found when the trace has no run there."""
    runs = list(
        (
            await session.exec(
                select(Run)
                .where(
                    Run.trace_id == trace_id,
                    Run.tenant_id == ctx.tenant_id,
                    Run.workspace_id == ctx.workspace_id,
                )
                .order_by(Run.started_at, Run.id)
            )
        ).all()
    )
    if not runs:
        raise NotFoundError(f"Trace not found: {trace_id}")
    steps = list(
        (
            await session.exec(
                select(RunStep)
                .where(
                    RunStep.trace_id == trace_id,
                    RunStep.tenant_id == ctx.tenant_id,
                    RunStep.workspace_id == ctx.workspace_id,
                )
                .order_by(RunStep.started_at, RunStep.id)
            )
        ).all()
    )
    return runs, steps
