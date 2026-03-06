"""models

ModelHub domain models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import Column, Text
from sqlmodel import SQLModel, Field, JSON

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


class PlatformModel(SQLModel, table=True):
    """Platform-wide model catalog entry."""

    __tablename__ = "platform_models"

    id: str = Field(primary_key=True, default_factory=lambda: f"plm_{generate_ulid()}")
    """Platform model ID."""

    tenant_id: str = Field(default="platform", index=True)
    """Platform tenant ID."""

    workspace_id: str = Field(default="platform", index=True)
    """Platform workspace ID."""

    provider_kind: str = Field(index=True)
    """Provider kind (openai, anthropic, gemini, etc.)."""

    model_id: str = Field(index=True)
    """Provider-native model identifier."""

    display_name: Optional[str] = Field(default=None, nullable=True)
    """Display name for UI."""

    capabilities_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Capabilities metadata."""

    context_window: Optional[int] = Field(default=None, nullable=True)
    """Context window size."""

    max_output_tokens: Optional[int] = Field(default=None, nullable=True)
    """Max output tokens."""

    lifecycle: Optional[str] = Field(default=None, nullable=True)
    """Lifecycle tag (beta/ga/deprecated)."""

    raw_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Raw metadata from provider."""

    is_active: bool = Field(default=True)
    """Whether the model is active upstream."""

    last_seen_at: Optional[datetime] = Field(default=None, nullable=True)
    """Last time the model was seen upstream."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class Provider(SQLModel, table=True):
    """Workspace-level provider configuration."""

    __tablename__ = "providers"

    id: str = Field(primary_key=True, default_factory=lambda: f"prov_{generate_ulid()}")
    """Provider ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    kind: str = Field(index=True)
    """Provider kind (openai, anthropic, gemini, openai_compat, etc.)."""

    name: str = Field(index=True)
    """Provider display name."""

    base_url: Optional[str] = Field(default=None, nullable=True)
    """Override base URL (required for openai_compat)."""

    credential_ref: Optional[str] = Field(default=None, nullable=True)
    """Secret reference for credentials."""

    status: str = Field(default="active")
    """Provider status (active/disabled/error)."""

    sync_policy_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Sync policy (auto_sync/interval/recreate_deleted/default_enabled)."""

    last_healthcheck_at: Optional[datetime] = Field(default=None, nullable=True)
    """Last healthcheck time."""

    last_healthcheck_error: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    """Last healthcheck error detail."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class ProviderModel(SQLModel, table=True):
    """Workspace-level provider model record."""

    __tablename__ = "provider_models"

    id: str = Field(primary_key=True, default_factory=lambda: f"pmod_{generate_ulid()}")
    """Provider model ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    provider_id: str = Field(index=True)
    """Provider ID."""

    provider_kind: str = Field(index=True)
    """Provider kind (redundant for filtering)."""

    model_id: str = Field(index=True)
    """Provider-native model identifier."""

    display_name: Optional[str] = Field(default=None, nullable=True)
    """Display name for UI."""

    description: Optional[str] = Field(default=None, nullable=True)
    """Description."""

    capabilities_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Capabilities metadata."""

    config_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Per-model configuration overrides (timeouts, etc.)."""

    context_window: Optional[int] = Field(default=None, nullable=True)
    """Context window size."""

    max_output_tokens: Optional[int] = Field(default=None, nullable=True)
    """Max output tokens."""

    lifecycle: Optional[str] = Field(default=None, nullable=True)
    """Lifecycle tag."""

    raw_meta: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Raw metadata from platform/provider."""

    enabled: bool = Field(default=True)
    """Whether the model is enabled in this workspace."""

    source: str = Field(default="platform")
    """Source of the model (platform/local)."""

    platform_model_id: Optional[str] = Field(default=None, nullable=True, index=True)
    """Associated platform model ID when source=platform."""

    sync_status: str = Field(default="never_synced")
    """Sync status (in_sync/diverged/platform_removed/never_synced)."""

    user_overrides_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """User overrides applied to platform fields."""

    last_synced_at: Optional[datetime] = Field(default=None, nullable=True)
    """Last sync time from platform."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class ProviderModelTombstone(SQLModel, table=True):
    """Tombstone for deleted platform models."""

    __tablename__ = "provider_model_tombstones"

    id: str = Field(primary_key=True, default_factory=lambda: f"tomb_{generate_ulid()}")
    """Tombstone ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    provider_id: str = Field(index=True)
    """Provider ID."""

    platform_model_id: str = Field(index=True)
    """Platform model ID."""

    deleted_at: datetime = Field(default_factory=utc_now)
    """Deletion timestamp."""


class SyncJob(SQLModel, table=True):
    """Provider sync job record."""

    __tablename__ = "provider_sync_jobs"

    id: str = Field(primary_key=True, default_factory=lambda: f"sync_{generate_ulid()}")
    """Sync job ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    provider_id: str = Field(index=True)
    """Provider ID."""

    status: str = Field(default="running")
    """Job status (running/succeeded/failed)."""

    diff_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    """Sync diff details."""

    error: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    """Error message."""

    started_at: datetime = Field(default_factory=utc_now)
    """Job start time."""

    ended_at: Optional[datetime] = Field(default=None, nullable=True)
    """Job end time."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""
