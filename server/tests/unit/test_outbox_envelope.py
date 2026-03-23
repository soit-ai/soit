"""Unit tests for outbox domain event envelope."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from app.kernel.events.envelope import DEFAULT_EVENT_VERSION, DomainEventEnvelope


def test_envelope_json_roundtrip_preserves_core_fields() -> None:
    occurred = datetime(2025, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
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
    occurred = datetime.now(timezone.utc)
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
