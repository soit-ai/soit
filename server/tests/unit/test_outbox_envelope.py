"""Unit tests for outbox domain event envelope."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from app.kernel.events.envelope import DEFAULT_EVENT_VERSION, DomainEventEnvelope
from app.kernel.events.payload_registry import (
    get_event_payload_version,
    is_registered_event_type,
)


def test_envelope_json_roundtrip_preserves_core_fields() -> None:
    occurred = datetime(2025, 3, 23, 12, 0, 0, tzinfo=UTC)
    original = DomainEventEnvelope(
        event_id="evt_01",
        event_type="run.created",
        event_version="2",
        tenant_id="t1",
        subject_type="run",
        subject_id="run_1",
        run_id="run_1",
        task_id=None,
        thread_id="thr_1",
        workflow_run_id=None,
        correlation_id="run_1",
        causation_id="evt_parent",
        producer="runtime",
        occurred_at=occurred,
        payload={"foo": 1},
    )
    dumped = json.dumps(original.to_json_dict())
    restored = DomainEventEnvelope.from_json_dict(json.loads(dumped))
    assert restored.event_id == "evt_01"
    assert restored.event_type == "run.created"
    assert restored.event_version == "2"
    assert restored.tenant_id == "t1"
    assert restored.subject_type == "run"
    assert restored.subject_id == "run_1"
    assert restored.run_id == "run_1"
    assert restored.thread_id == "thr_1"
    assert restored.correlation_id == "run_1"
    assert restored.causation_id == "evt_parent"
    assert restored.producer == "runtime"
    assert restored.occurred_at == occurred
    assert restored.payload == {"foo": 1}


def test_envelope_default_version_and_optional_omitted() -> None:
    occurred = datetime.now(UTC)
    env = DomainEventEnvelope(
        event_id="evt_02",
        event_type="task.completed",
        occurred_at=occurred,
    )
    data = env.to_json_dict()
    assert data["event_version"] == DEFAULT_EVENT_VERSION
    roundtrip = DomainEventEnvelope.from_json_dict(data)
    assert roundtrip.task_id is None
    assert roundtrip.payload == {}


def test_registered_kernel_events_have_payload_versions() -> None:
    assert get_event_payload_version("task.created") == "1"
    assert get_event_payload_version("task.status") == "1"
    assert get_event_payload_version("run.created") == "1"
    assert get_event_payload_version("run.status.updated") == "1"
    assert get_event_payload_version("response.completed") == "1"
    assert get_event_payload_version("approval.approved") == "1"
    assert is_registered_event_type("unknown.compat.event") is False
