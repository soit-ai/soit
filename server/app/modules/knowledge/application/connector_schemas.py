"""Schemas for knowledge sources and their sync runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceLimitsPayload(BaseModel):
    """Per-run caps a source may set; an omitted cap takes the deployment default."""

    max_items: int | None = Field(default=None, ge=1)
    max_item_bytes: int | None = Field(default=None, ge=1)
    max_total_bytes: int | None = Field(default=None, ge=1)


class SourceCreateRequest(BaseModel):
    """Create a source on a knowledge base."""

    name: str = Field(..., min_length=1, max_length=128)
    connector_kind: str = Field(..., min_length=1, max_length=32)
    config: dict[str, Any] = Field(default_factory=dict)
    secret_id: str | None = None
    """Opaque id of an existing secret holding the connector's credentials."""

    schedule_cron: str | None = None
    schedule_timezone: str = "UTC"
    enabled: bool = True
    delete_removed: bool = False
    limits: SourceLimitsPayload | None = None


class SourceUpdateRequest(BaseModel):
    """Change a source; only the fields sent are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    config: dict[str, Any] | None = None
    secret_id: str | None = None
    schedule_cron: str | None = None
    schedule_timezone: str | None = None
    enabled: bool | None = None
    delete_removed: bool | None = None
    limits: SourceLimitsPayload | None = None


class SourceTestRequest(BaseModel):
    """Test a connection that has not been saved yet."""

    connector_kind: str = Field(..., min_length=1, max_length=32)
    config: dict[str, Any] = Field(default_factory=dict)
    secret_id: str | None = None


class EffectiveLimits(BaseModel):
    max_items: int
    max_item_bytes: int
    max_total_bytes: int


class SourceResponse(BaseModel):
    """A source as the API shows it. Credentials are never part of it."""

    id: str
    tenant_id: str
    workspace_id: str
    knowledge_id: str
    name: str
    connector_kind: str
    config: dict[str, Any]
    secret_id: str | None
    limits: EffectiveLimits
    schedule_cron: str | None
    schedule_timezone: str
    enabled: bool
    delete_removed: bool
    next_sync_at: datetime | None
    last_sync_at: datetime | None
    last_status: str | None
    last_error: str | None
    last_counts: dict[str, Any]
    active_run_id: str | None = None
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class SyncRunResponse(BaseModel):
    """One sync run."""

    id: str
    tenant_id: str
    workspace_id: str
    knowledge_id: str
    source_id: str
    trigger: Literal["manual", "schedule"] | str
    status: str
    added_count: int
    updated_count: int
    unchanged_count: int
    removed_count: int
    failed_count: int
    skipped_count: int
    truncated: bool
    error_code: str | None
    error_message: str | None
    cancel_requested: bool
    requested_by: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SyncRunDetailResponse(SyncRunResponse):
    """A run with its per-item outcomes (every outcome except unchanged, capped)."""

    outcomes: list[dict[str, Any]] = Field(default_factory=lambda: [])


class ConnectionSampleItem(BaseModel):
    external_id: str
    name: str
    size: int | None = None
    modified: str | None = None
    content_type: str | None = None


class ConnectionTestResponse(BaseModel):
    ok: bool
    message: str
    sample: list[ConnectionSampleItem] = Field(default_factory=lambda: [])


class ConnectorFieldOption(BaseModel):
    value: str
    label: str


class ConnectorFieldResponse(BaseModel):
    key: str
    label: str
    type: str
    required: bool
    default: Any = None
    help: str | None = None
    placeholder: str | None = None
    options: list[ConnectorFieldOption] = Field(default_factory=lambda: [])
    minimum: int | None = None
    maximum: int | None = None


class ConnectorResponse(BaseModel):
    """A connector kind and the configuration it takes."""

    kind: str
    label: str
    description: str
    fields: list[ConnectorFieldResponse]
    secret: str
    secret_help: str | None = None
