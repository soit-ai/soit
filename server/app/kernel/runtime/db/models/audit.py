"""Unified audit event model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Index
from sqlmodel import JSON, Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


class AuditEvent(SQLModel, table=True):
    """Append-only audit event for cross-module governance changes."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_scope_created", "tenant_id", "workspace_id", "created_at"),
        Index("ix_audit_events_resource", "tenant_id", "workspace_id", "resource_type", "resource_id"),
        Index("ix_audit_events_event_type_created", "event_type", "created_at"),
        Index("ix_audit_events_scope_run_created", "tenant_id", "workspace_id", "run_id", "created_at"),
    )

    id: str = Field(primary_key=True, default_factory=generate_ulid)
    tenant_id: str = Field(index=True)
    workspace_id: str | None = Field(default=None, nullable=True, index=True)
    event_type: str = Field(index=True)
    resource_type: str = Field(index=True)
    resource_id: str | None = Field(default=None, nullable=True, index=True)
    run_id: str | None = Field(default=None, nullable=True, index=True)
    step_id: str | None = Field(default=None, nullable=True, index=True)
    trace_id: str | None = Field(default=None, nullable=True, index=True)
    outcome: str | None = Field(default=None, nullable=True, index=True)
    evidence_artifact_id: str | None = Field(default=None, nullable=True, index=True)
    operation: str = Field(index=True)
    actor_user_id: str | None = Field(default=None, nullable=True, index=True)
    subject_user_id: str | None = Field(default=None, nullable=True, index=True)
    scope: str | None = Field(default=None, nullable=True, index=True)
    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now, index=True)

    @property
    def created_by(self) -> str | None:
        return self.actor_user_id

    @property
    def allowlist(self) -> list[str]:
        value = self.payload_json.get("allowlist", [])
        return list(value) if isinstance(value, list) else []

    @property
    def blocklist(self) -> list[str]:
        value = self.payload_json.get("blocklist", [])
        return list(value) if isinstance(value, list) else []
