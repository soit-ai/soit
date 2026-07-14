"""Domain event envelope for transactional outbox (Phase 1).

Field set aligns with server/docs/architecture/OUTBOX_EVENT_MODEL.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_EVENT_VERSION = "1"


class DomainEventEnvelope(BaseModel):
    """Canonical shape of a domain fact stored in event_outbox and dispatched."""

    event_id: str
    event_type: str
    event_version: str = Field(default=DEFAULT_EVENT_VERSION)
    tenant_id: str | None = None
    workspace_id: str | None = None
    idempotency_key: str | None = None
    subject_type: str | None = None
    subject_id: str | None = None
    run_id: str | None = None
    task_id: str | None = None
    thread_id: str | None = None
    workflow_run_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    producer: str | None = None
    occurred_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    def to_json_dict(self) -> dict[str, Any]:
        """Serialize for JSON column storage (ISO-8601 datetimes)."""
        return self.model_dump(mode="json")

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> DomainEventEnvelope:
        """Deserialize from DB or API payload."""
        return cls.model_validate(data)
