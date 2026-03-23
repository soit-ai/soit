"""Domain event envelope for transactional outbox (Phase 1).

Field set aligns with docs/SOIT_Minimal_Outbox_EventDriven_Design_Checklist.md §5.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


DEFAULT_EVENT_VERSION = "1"


class DomainEventEnvelope(BaseModel):
    """Canonical shape of a domain fact stored in event_outbox and dispatched."""

    event_id: str
    event_type: str
    event_version: str = Field(default=DEFAULT_EVENT_VERSION)
    tenant_id: Optional[str] = None
    subject_type: Optional[str] = None
    subject_id: Optional[str] = None
    run_id: Optional[str] = None
    task_id: Optional[str] = None
    thread_id: Optional[str] = None
    workflow_run_id: Optional[str] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    producer: Optional[str] = None
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
