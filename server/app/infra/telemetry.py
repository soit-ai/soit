"""OpenTelemetry SDK configuration for API and worker processes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

from app.settings.settings import settings

logger = logging.getLogger(__name__)
_configured_provider: TracerProvider | None = None
_libraries_instrumented = False


def build_tracer_provider(
    *,
    service_name: str,
    exporter: SpanExporter,
    sample_ratio: float = 1.0,
    batch: bool = True,
) -> TracerProvider:
    """Build an SDK provider with a concrete exporter and service resource."""
    ratio = min(1.0, max(0.0, float(sample_ratio)))
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": service_name,
                "service.version": settings.platform_version,
                "deployment.environment.name": settings.environment,
            }
        ),
        sampler=ParentBased(TraceIdRatioBased(ratio)),
    )
    processor = BatchSpanProcessor(exporter) if batch else SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    return provider


def configure_telemetry(
    app: FastAPI | None = None,
    *,
    service_name: str | None = None,
) -> TracerProvider | None:
    """Configure OTLP tracing and standard library instrumentation once per process."""
    global _configured_provider, _libraries_instrumented
    if not settings.otel_enabled:
        return None
    if _configured_provider is None:
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
        _configured_provider = build_tracer_provider(
            service_name=service_name or settings.otel_service_name,
            exporter=exporter,
            sample_ratio=settings.otel_traces_sample_ratio,
        )
        trace.set_tracer_provider(_configured_provider)

    if not _libraries_instrumented:
        HTTPXClientInstrumentor().instrument(tracer_provider=_configured_provider)
        SQLAlchemyInstrumentor().instrument(tracer_provider=_configured_provider)
        redis_instrumentor: Any = RedisInstrumentor()
        redis_instrumentor.instrument(tracer_provider=_configured_provider)
        CeleryInstrumentor().instrument(  # type: ignore[no-untyped-call]
            tracer_provider=_configured_provider
        )
        _libraries_instrumented = True
    if app is not None:
        FastAPIInstrumentor.instrument_app(app, tracer_provider=_configured_provider)
    logger.info(
        "OpenTelemetry tracing configured",
        extra={"service_name": service_name or settings.otel_service_name},
    )
    return _configured_provider
