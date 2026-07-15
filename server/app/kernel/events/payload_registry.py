"""Payload version registry for kernel domain events."""

from __future__ import annotations

from dataclasses import dataclass

from app.kernel.events.envelope import DEFAULT_EVENT_VERSION


@dataclass(frozen=True)
class EventPayloadSpec:
    """Registered event payload contract."""

    event_type: str
    version: str = DEFAULT_EVENT_VERSION


_EVENT_PAYLOADS: dict[str, EventPayloadSpec] = {
    "approval.approved": EventPayloadSpec("approval.approved"),
    "approval.rejected": EventPayloadSpec("approval.rejected"),
    "response.canceled": EventPayloadSpec("response.canceled"),
    "response.succeeded": EventPayloadSpec("response.succeeded"),
    "response.created": EventPayloadSpec("response.created"),
    "response.failed": EventPayloadSpec("response.failed"),
    "response.input.added": EventPayloadSpec("response.input.added"),
    "response.output_text.done": EventPayloadSpec("response.output_text.done"),
    "response.output_text.delta": EventPayloadSpec("response.output_text.delta"),
    "run.created": EventPayloadSpec("run.created"),
    "run.status": EventPayloadSpec("run.status"),
    "run.status.updated": EventPayloadSpec("run.status.updated"),
    "run.updated": EventPayloadSpec("run.updated"),
    "task.checkpoint": EventPayloadSpec("task.checkpoint"),
    "task.checkpointed": EventPayloadSpec("task.checkpointed"),
    "task.completed": EventPayloadSpec("task.completed"),
    "task.created": EventPayloadSpec("task.created"),
    "task.failed": EventPayloadSpec("task.failed"),
    "task.retried": EventPayloadSpec("task.retried"),
    "task.retry": EventPayloadSpec("task.retry"),
    "task.started": EventPayloadSpec("task.started"),
    "task.status": EventPayloadSpec("task.status"),
}


def is_registered_event_type(event_type: str) -> bool:
    """Return whether the event type has a kernel payload contract."""

    return event_type in _EVENT_PAYLOADS


def get_event_payload_version(event_type: str, default: str = DEFAULT_EVENT_VERSION) -> str:
    """Return registered payload version or a compatibility default."""

    spec = _EVENT_PAYLOADS.get(event_type)
    return spec.version if spec else default


def validate_event_payload_version(event_type: str, event_version: str) -> None:
    """Validate version for registered events while preserving unknown-event compatibility."""

    spec = _EVENT_PAYLOADS.get(event_type)
    if not spec:
        return
    if str(event_version) != spec.version:
        raise ValueError(
            f"event_version mismatch for {event_type}: expected {spec.version}, got {event_version}"
        )


def registered_event_types() -> list[str]:
    """Return registered event types for diagnostics and architecture tests."""

    return sorted(_EVENT_PAYLOADS)


__all__ = [
    "EventPayloadSpec",
    "get_event_payload_version",
    "is_registered_event_type",
    "registered_event_types",
    "validate_event_payload_version",
]
