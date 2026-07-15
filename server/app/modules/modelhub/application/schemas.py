"""schemas

ModelHub application schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProviderCreate(BaseModel):
    """Provider creation schema."""

    kind: str
    adapter_backend: Literal["native", "litellm"] = "native"
    slug: str | None = None
    name: str
    base_url: str | None = None
    credential_ref: str | None = None
    status: str = "active"
    sync_policy_json: dict[str, Any] | None = None
    connection_config_json: dict[str, Any] | None = None
    auth_config_json: dict[str, Any] | None = None
    runtime_config_json: dict[str, Any] | None = None
    governance_config_json: dict[str, Any] | None = None


class ProviderUpdate(BaseModel):
    """Provider update schema."""

    kind: str | None = None
    adapter_backend: Literal["native", "litellm"] | None = None
    slug: str | None = None
    name: str | None = None
    base_url: str | None = None
    credential_ref: str | None = None
    status: str | None = None
    sync_policy_json: dict[str, Any] | None = None
    connection_config_json: dict[str, Any] | None = None
    auth_config_json: dict[str, Any] | None = None
    runtime_config_json: dict[str, Any] | None = None
    governance_config_json: dict[str, Any] | None = None


class ProviderResponse(BaseModel):
    """Provider response schema."""

    id: str
    kind: str
    adapter_backend: Literal["native", "litellm"]
    slug: str | None = None
    name: str
    base_url: str | None = None
    credential_ref: str | None = None
    status: str
    sync_policy_json: dict[str, Any] | None = None
    connection_config_json: dict[str, Any] | None = None
    auth_config_json: dict[str, Any] | None = None
    runtime_config_json: dict[str, Any] | None = None
    governance_config_json: dict[str, Any] | None = None
    last_synced_at: datetime | None = None
    last_healthcheck_at: datetime | None = None
    last_healthcheck_error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlatformModelResponse(BaseModel):
    """Platform model response schema."""

    id: str
    provider_kind: str
    model_id: str
    display_name: str | None = None
    capabilities_json: dict[str, Any] | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    status: str
    lifecycle_status: str | None = None
    raw_meta: dict[str, Any] | None = None
    last_seen_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProviderModelCreate(BaseModel):
    """Provider model creation schema."""

    model_config = ConfigDict(extra="forbid")

    model_id: str
    display_name: str | None = None
    description: str | None = None
    capabilities_json: dict[str, Any] | None = None
    config_json: dict[str, Any] | None = None
    architecture_json: dict[str, Any] | None = None
    capability_matrix_json: dict[str, Any] | None = None
    parameter_config_json: dict[str, Any] | None = None
    pricing_json: dict[str, Any] | None = None
    diagnostics_json: dict[str, Any] | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    lifecycle_status: str | None = None
    raw_meta: dict[str, Any] | None = None
    user_overrides_json: dict[str, Any] | None = None
    source: str | None = None
    platform_model_id: str | None = None
    last_synced_at: datetime | None = None
    status: str = "active"


class ProviderModelUpdate(BaseModel):
    """Provider model update schema."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    description: str | None = None
    capabilities_json: dict[str, Any] | None = None
    config_json: dict[str, Any] | None = None
    architecture_json: dict[str, Any] | None = None
    capability_matrix_json: dict[str, Any] | None = None
    parameter_config_json: dict[str, Any] | None = None
    pricing_json: dict[str, Any] | None = None
    diagnostics_json: dict[str, Any] | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    lifecycle_status: str | None = None
    raw_meta: dict[str, Any] | None = None
    user_overrides_json: dict[str, Any] | None = None
    source: str | None = None
    platform_model_id: str | None = None
    last_synced_at: datetime | None = None
    status: str | None = None


class ProviderModelResponse(BaseModel):
    """Provider model response schema."""

    id: str
    provider_id: str
    provider_kind: str
    model_id: str
    model_ref: str
    display_name: str | None = None
    description: str | None = None
    capabilities_json: dict[str, Any] | None = None
    config_json: dict[str, Any] | None = None
    architecture_json: dict[str, Any] | None = None
    capability_matrix_json: dict[str, Any] | None = None
    parameter_config_json: dict[str, Any] | None = None
    pricing_json: dict[str, Any] | None = None
    diagnostics_json: dict[str, Any] | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    status: str
    lifecycle_status: str | None = None
    raw_meta: dict[str, Any] | None = None
    source: str
    platform_model_id: str | None = None
    sync_status: str
    user_overrides_json: dict[str, Any] | None = None
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SyncFromPlatformRequest(BaseModel):
    """Sync from platform request schema."""

    include_model_ids: list[str] | None = None


class SyncJobResponse(BaseModel):
    """Sync job response schema."""

    id: str
    provider_id: str
    status: str
    diff_json: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthcheckResponse(BaseModel):
    """Provider healthcheck response schema."""

    status: str
    message: str | None = None
    checked_at: datetime


class ProviderSupportStatusResponse(BaseModel):
    """Provider support and workspace configuration status."""

    provider_kind: str
    display_name: str
    support_status: str
    configured: bool
    provider_count: int = 0
    configured_provider_ids: list[str] = Field(default_factory=list)
    chat_supported: bool
    embeddings_supported: bool
    catalog_supported: bool
    notes: str | None = None


class AdapterBackendSupportResponse(BaseModel):
    """Runtime installation status for an LLM adapter backend."""

    adapter_backend: str
    display_name: str
    available: bool
    install_hint: str | None = None


class ProviderPresetResponse(BaseModel):
    """Server-owned provider configuration preset."""

    provider_kind: str
    display_name: str
    default_adapter_backend: str
    supported_adapter_backends: list[str] = Field(default_factory=list)
    litellm_provider: str
    requires_base_url: bool
    credential_optional: bool


class ProviderSupportMatrixResponse(BaseModel):
    """Provider support matrix for the MVP ModelHub surface."""

    providers: list[ProviderSupportStatusResponse]
    adapter_backends: list[AdapterBackendSupportResponse] = Field(default_factory=list)
    provider_presets: list[ProviderPresetResponse] = Field(default_factory=list)


class ModelWorkbenchSummary(BaseModel):
    """ModelHub workbench aggregate metrics."""

    total_models: int
    available_models: int
    total_providers: int
    online_providers: int
    month_calls: int
    month_tokens: int
    month_cost_amount: float
    currency: str | None = None
    avg_latency_ms: int | None = None
    abnormal_models: int
    updated_at: datetime


class ModelWorkbenchModelTabs(BaseModel):
    """Counts for model workbench model filters."""

    all: int
    text: int
    embedding: int
    multimodal: int
    rerank: int
    disabled: int
    abnormal: int


class ModelWorkbenchProviderTabs(BaseModel):
    """Counts for model workbench provider filters."""

    all: int
    online: int
    disabled: int
    error: int


class ModelWorkbenchModelRow(BaseModel):
    """Model row with runtime usage metrics."""

    id: str
    provider_id: str
    provider_name: str
    provider_kind: str
    model_id: str
    display_name: str | None = None
    description: str | None = None
    model_type: str
    status: str
    context_window: int | None = None
    max_output_tokens: int | None = None
    lifecycle_status: str | None = None
    sync_status: str
    source: str
    month_calls: int
    today_calls: int
    month_tokens: int
    month_cost_amount: float
    currency: str | None = None
    avg_latency_ms: int | None = None
    recent_exception_count: int
    last_run_at: datetime | None = None
    last_synced_at: datetime | None = None
    updated_at: datetime
    owner: str | None = None
    region: str | None = None
    unit_price: float | None = None
    action_enabled: bool


class ModelWorkbenchProviderRow(BaseModel):
    """Provider row with model and runtime usage metrics."""

    id: str
    name: str
    kind: str
    status: str
    available_models: int
    total_models: int
    model_types: list[str] = Field(default_factory=list)
    month_calls: int
    month_tokens: int
    month_cost_amount: float
    currency: str | None = None
    avg_latency_ms: int | None = None
    recent_exception_count: int
    availability: float | None = None
    last_sync_at: datetime | None = None
    last_healthcheck_at: datetime | None = None
    updated_at: datetime
    owner: str | None = None
    region: str | None = None
    quota_used: float | None = None
    quota_limit: float | None = None
    quota_percent: float | None = None


class ModelWorkbenchTrendPoint(BaseModel):
    """Daily model usage point."""

    date: str
    calls: int
    tokens: int
    cost_amount: float
    avg_latency_ms: int | None = None


class ModelWorkbenchCostShareRow(BaseModel):
    """Cost share row for charts."""

    id: str
    label: str
    provider_kind: str | None = None
    value: float
    currency: str | None = None


class ModelWorkbenchQuotaReminderRow(BaseModel):
    """Quota reminder row with nullable quota fields when unavailable."""

    id: str
    label: str
    status: str
    quota_used: float | None = None
    quota_limit: float | None = None
    quota_percent: float | None = None
    remaining_quota: float | None = None


class ModelWorkbenchOverviewResponse(BaseModel):
    """Full ModelHub overview response."""

    summary: ModelWorkbenchSummary
    model_tabs: ModelWorkbenchModelTabs
    provider_tabs: ModelWorkbenchProviderTabs
    trend: list[ModelWorkbenchTrendPoint] = Field(default_factory=list)
    cost_share: list[ModelWorkbenchCostShareRow] = Field(default_factory=list)
    top_models: list[ModelWorkbenchModelRow] = Field(default_factory=list)
    top_providers: list[ModelWorkbenchProviderRow] = Field(default_factory=list)
    quota_reminders: list[ModelWorkbenchQuotaReminderRow] = Field(default_factory=list)


class ModelWorkbenchModelsResponse(BaseModel):
    """Paginated model workbench rows."""

    summary: ModelWorkbenchSummary
    tabs: ModelWorkbenchModelTabs
    items: list[ModelWorkbenchModelRow]
    next_page_token: str | None = None
    page_size: int


class ModelWorkbenchProvidersResponse(BaseModel):
    """Paginated provider workbench rows."""

    summary: ModelWorkbenchSummary
    tabs: ModelWorkbenchProviderTabs
    items: list[ModelWorkbenchProviderRow]
    next_page_token: str | None = None
    page_size: int


class ModelTestChatRequest(BaseModel):
    """Model chat test request schema."""

    provider_id: str
    model_id: str
    input: str = Field(min_length=1)


class ModelTestEmbeddingRequest(BaseModel):
    """Model embedding test request schema."""

    provider_id: str
    model_id: str
    input: str = Field(min_length=1)


class ModelTestResponse(BaseModel):
    """Model test response schema."""

    success: bool
    message: str
    response: str | None = None
    latency_ms: int | None = None
    tokens_prompt: int | None = None
    tokens_completion: int | None = None
    request_id: str | None = None
