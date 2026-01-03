""" tracing

Tracing hooks (OTel).

This project keeps tracing pluggable. If OpenTelemetry is configured in the
runtime environment, you can wire real OTel exporters/instrumentors here.

For OSS/local runs, we provide a lightweight, safe default implementation that:
- Creates a request_id/trace_id per request (middleware).
- Emits structured trace events via Python logging.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, Callable
import json
import logging
import uuid

from fastapi import FastAPI, Request, Response

from app.kernel.trace.models import Run, RunStep


logger = logging.getLogger(__name__)


class OpenTelemetryTracer:
    """A lightweight tracer façade.

    It does **not** require OpenTelemetry packages to be installed. In a production
    deployment you can replace its internals with real OTel spans/export.
    """

    def __init__(self, emit: Optional[Callable[[str, Dict[str, Any]], None]] = None):
        """Initialize tracer.

        Args:
            emit: Optional custom emitter for trace events.
        """
        self._emit = emit or self._default_emit

    def _default_emit(self, event: str, payload: Dict[str, Any]) -> None:
        try:
            logger.info("trace.%s %s", event, json.dumps(payload, ensure_ascii=False, default=str))
        except Exception:
            logger.info("trace.%s %s", event, payload)

    def trace_run(self, run: Run, attrs: Optional[Dict[str, Any]] = None) -> None:
        """Emit a run-level trace event."""
        payload: Dict[str, Any] = {"run_id": run.id, "status": run.status}
        if attrs:
            payload.update(attrs)
        self._emit("run", payload)

    def trace_step(self, step: RunStep, attrs: Optional[Dict[str, Any]] = None) -> None:
        """Emit a step-level trace event."""
        payload: Dict[str, Any] = {
            "run_id": step.run_id,
            "step_id": step.id,
            "step_type": step.step_type,
            "status": step.status,
        }
        if attrs:
            payload.update(attrs)
        self._emit("step", payload)


# Global tracer instance
tracer = OpenTelemetryTracer()


def setup_tracing(app: FastAPI) -> None:
    """Setup tracing for FastAPI application.

    Adds a small middleware that:
    - Ensures `X-Request-Id` exists (generates one if missing).
    - Stores ids on `request.state` so downstream code can attach them to logs.
    """

    @app.middleware("http")
    async def _trace_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        trace_id = request.headers.get("X-Trace-Id") or request_id

        request.state.request_id = request_id
        request.state.trace_id = trace_id

        response: Response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Trace-Id"] = trace_id
        return response
