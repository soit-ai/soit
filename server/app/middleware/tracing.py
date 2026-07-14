"""tracing

FastAPI tracing middleware.

This middleware integrates with kernel tracing (OpenTelemetryTracer) but stays
outside of kernel to avoid coupling kernel to FastAPI.
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request, Response
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware

from app.kernel.observe.context import (
    clear_request_context,
    clear_run_context,
    clear_step_context,
    get_log_context,
    set_request_context,
)

logger = logging.getLogger(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """HTTP middleware that injects request/trace ids and logs latency."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-Id") or getattr(request.state, "request_id", None) or str(uuid.uuid4())
        span_context = trace.get_current_span().get_span_context()
        otel_trace_id = f"{span_context.trace_id:032x}" if span_context.is_valid else None
        trace_id = (
            otel_trace_id
            or request.headers.get("X-Trace-Id")
            or getattr(request.state, "trace_id", None)
            or request_id
        )
        workspace_id = request.headers.get("X-Workspace-Id") or getattr(request.state, "workspace_id", None)

        request.state.request_id = request_id
        request.state.trace_id = trace_id
        request.state.workspace_id = workspace_id
        set_request_context(request_id=request_id, trace_id=trace_id, workspace_id=workspace_id)

        start = time.monotonic()
        response: Response | None = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            latency_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "http.request",
                extra={
                    "http_method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                },
            )
            if response is not None:
                response.headers["X-Request-Id"] = request_id
                response.headers["X-Trace-Id"] = trace_id
                log_ctx = get_log_context()
                run_id = log_ctx.get("run_id")
                if run_id:
                    response.headers["X-Run-Id"] = str(run_id)
            clear_request_context()
            clear_run_context()
            clear_step_context()


def setup_tracing(app: FastAPI) -> None:
    """Register tracing middleware on a FastAPI app."""
    app.add_middleware(TracingMiddleware)
