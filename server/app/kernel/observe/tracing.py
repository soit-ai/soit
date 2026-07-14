"""Product execution spans linked to SOIT run and step audit records."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Tracer

from app.kernel.runtime.db.models.runs import Run, RunStep

logger = logging.getLogger(__name__)


class OpenTelemetryTracer:
    """Emit real OTel spans while preserving structured trace event logs."""

    def __init__(
        self,
        emit: Callable[[str, dict[str, Any]], None] | None = None,
        *,
        otel_tracer: Tracer | None = None,
    ) -> None:
        self._emit = emit or self._default_emit
        self._tracer = otel_tracer or trace.get_tracer("soit.execution")

    def _default_emit(self, event: str, payload: dict[str, Any]) -> None:
        try:
            logger.info(
                "trace.%s %s",
                event,
                json.dumps(payload, ensure_ascii=False, default=str),
            )
        except Exception:
            logger.info("trace.%s %s", event, payload)

    @staticmethod
    def _set_attributes(span: trace.Span, payload: dict[str, Any]) -> None:
        for key, value in payload.items():
            if value is None:
                continue
            if isinstance(value, str | bool | int | float):
                span.set_attribute(f"soit.{key.replace('_', '.')}", value)

    def trace_run(self, run: Run, attrs: dict[str, Any] | None = None) -> None:
        """Record a run lifecycle span with stable product identifiers."""
        payload: dict[str, Any] = {
            "run_id": run.id,
            "tenant_id": run.tenant_id,
            "workspace_id": run.workspace_id,
            "status": run.status,
        }
        if attrs:
            payload.update(attrs)
        event = str(payload.get("event") or "event")
        with self._tracer.start_as_current_span(f"soit.run.{event}") as span:
            self._set_attributes(span, payload)
        self._emit("run", payload)

    def trace_step(self, step: RunStep, attrs: dict[str, Any] | None = None) -> None:
        """Record a step lifecycle span linked to its run and audit row."""
        payload: dict[str, Any] = {
            "run_id": step.run_id,
            "step_id": step.id,
            "tenant_id": step.tenant_id,
            "workspace_id": step.workspace_id,
            "step_type": step.step_type,
            "status": step.status,
        }
        if attrs:
            payload.update(attrs)
        event = str(payload.get("event") or "event")
        with self._tracer.start_as_current_span(f"soit.step.{event}") as span:
            self._set_attributes(span, payload)
        self._emit("step", payload)


tracer = OpenTelemetryTracer()
