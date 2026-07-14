"""Unit tests for OutboxPublisher thin wrapper."""

from __future__ import annotations

from datetime import UTC, datetime

from opentelemetry import trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, use_span

from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.publisher import OutboxPublisher


def test_publisher_delegates_enqueue_to_repository(db) -> None:
    env = DomainEventEnvelope(
        event_id="evt_pub",
        event_type="t",
        occurred_at=datetime(2025, 3, 23, 12, 0, 0, tzinfo=UTC),
        payload={"a": 1},
    )
    repo = OutboxRepository(db)
    pub = OutboxPublisher(repo)
    row = pub.publish(env, headers_json={"h": "1"})
    db.commit()
    loaded = repo.get(row.id)
    assert loaded is not None
    assert loaded.event_id == "evt_pub"
    assert loaded.headers_json == {"h": "1"}


def test_publisher_propagates_w3c_trace_and_scope_headers(db) -> None:
    repo = OutboxRepository(db)
    pub = OutboxPublisher(repo)
    span_context = SpanContext(
        trace_id=int("1234567890abcdef1234567890abcdef", 16),
        span_id=int("1234567890abcdef", 16),
        is_remote=False,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
        trace_state=trace.DEFAULT_TRACE_STATE,
    )
    envelope = DomainEventEnvelope(
        event_id="evt_trace_context",
        event_type="run.created",
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        occurred_at=datetime.now(UTC),
    )

    with use_span(NonRecordingSpan(span_context), end_on_exit=False):
        row = pub.publish(envelope)

    assert row.headers_json is not None
    assert row.headers_json["traceparent"] == (
        "00-1234567890abcdef1234567890abcdef-1234567890abcdef-01"
    )
    assert row.headers_json["tenant_id"] == "tenant-a"
    assert row.headers_json["workspace_id"] == "workspace-a"
