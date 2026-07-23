"""models

ModelHub domain models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, Index, String, Text, UniqueConstraint
from sqlmodel import JSON, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


class PlatformModel(SQLModel, table=True):
    """Platform-wide model catalog entry."""

    __tablename__ = "platform_models"
    __table_args__ = (
        UniqueConstraint(
            "provider_kind",
            "model_id",
            name="uq_platform_models_provider_kind_model_id",
        ),
    )

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

    display_name: str | None = Field(default=None, nullable=True)
    """Display name for UI."""

    capabilities_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Capabilities metadata."""

    context_window: int | None = Field(default=None, nullable=True)
    """Context window size."""

    max_output_tokens: int | None = Field(default=None, nullable=True)
    """Max output tokens."""

    lifecycle_status: str | None = Field(default=None, nullable=True)
    """Lifecycle tag (beta/ga/deprecated)."""

    raw_meta: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Raw metadata from provider."""

    status: str = Field(default="active", index=True)
    """Model status (active/disabled/removed)."""

    last_seen_at: datetime | None = Field(default=None, nullable=True)
    """Last time the model was seen upstream."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class Provider(SQLModel, table=True):
    """Workspace-level provider configuration."""

    __tablename__ = "providers"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "slug",
            name="uq_providers_scope_slug",
        ),
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "name",
            name="uq_providers_scope_name",
        ),
        Index("ix_providers_scope_status", "tenant_id", "workspace_id", "status"),
    )

    id: str = Field(primary_key=True, default_factory=lambda: f"prov_{generate_ulid()}")
    """Provider ID."""

    tenant_id: str = Field(index=True)
    """Tenant ID."""

    workspace_id: str = Field(index=True)
    """Workspace ID."""

    kind: str = Field(index=True)
    """Provider kind (openai, anthropic, gemini, openai_compatible, etc.)."""

    adapter_backend: str = Field(default="native", index=True)
    """Runtime adapter backend (native or litellm)."""

    slug: str | None = Field(default=None, index=True, nullable=True)
    """Workspace-readable provider slug."""

    name: str = Field(index=True)
    """Provider display name."""

    base_url: str | None = Field(default=None, nullable=True)
    """Override base URL (required for OpenAI-compatible providers)."""

    credential_secret_id: str | None = Field(
        default=None,
        sa_column=Column("credential_ref", String, nullable=True),
    )
    """Opaque secret ID for credentials; the physical column remains compatible."""

    status: str = Field(default="active")
    """Provider status (active/disabled/error)."""

    sync_policy_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Sync policy (auto_sync/interval/recreate_deleted/default_enabled)."""

    connection_config_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Connection config (version/timeout/retry/rate limits)."""

    auth_config_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Authentication config."""

    runtime_config_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Runtime and diagnostics support config."""

    governance_config_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Governance, cost, and observability config."""

    last_healthcheck_at: datetime | None = Field(default=None, nullable=True)
    """Last healthcheck time."""

    last_healthcheck_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    """Last healthcheck error detail."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


class ProviderModel(SQLModel, table=True):
    """Workspace-level provider model record."""

    __tablename__ = "provider_models"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "provider_id",
            "model_id",
            name="uq_provider_models_scope_provider_model_id",
        ),
        Index(
            "ix_provider_models_scope_status",
            "tenant_id",
            "workspace_id",
            "status",
        ),
    )

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

    display_name: str | None = Field(default=None, nullable=True)
    """Display name for UI."""

    description: str | None = Field(default=None, nullable=True)
    """Description."""

    capabilities_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Capabilities metadata."""

    config_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Per-model configuration overrides (timeouts, etc.)."""

    architecture_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Model architecture and modality configuration."""

    capability_matrix_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Merged catalog, diagnostics, runtime, and user override capability matrix."""

    parameter_config_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Supported parameters, default parameters, and model-specific input limits."""

    pricing_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Model pricing and billing-unit configuration."""

    diagnostics_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Model diagnostics, trust status, and runtime statistics configuration."""

    context_window: int | None = Field(default=None, nullable=True)
    """Context window size."""

    max_output_tokens: int | None = Field(default=None, nullable=True)
    """Max output tokens."""

    lifecycle_status: str | None = Field(default=None, nullable=True)
    """Lifecycle tag."""

    raw_meta: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Raw metadata from platform/provider."""

    status: str = Field(default="active", index=True)
    """Model status (active/disabled)."""

    source: str = Field(default="platform")
    """Source of the model (platform/local)."""

    platform_model_id: str | None = Field(default=None, nullable=True, index=True)
    """Associated platform model ID when source=platform."""

    sync_status: str = Field(default="never_synced")
    """Sync status (in_sync/diverged/platform_removed/user_removed/never_synced)."""

    user_overrides_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """User overrides applied to platform fields."""

    last_synced_at: datetime | None = Field(default=None, nullable=True)
    """Last sync time from platform."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""


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

    diff_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    """Sync diff details."""

    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    """Error message."""

    started_at: datetime = Field(default_factory=utc_now)
    """Job start time."""

    ended_at: datetime | None = Field(default=None, nullable=True)
    """Job end time."""

    created_at: datetime = Field(default_factory=utc_now)
    """Creation timestamp."""

    updated_at: datetime = Field(default_factory=utc_now)
    """Last update timestamp."""
