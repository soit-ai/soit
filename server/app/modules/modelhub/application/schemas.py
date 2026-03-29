"""schemas

ModelHub application schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, ConfigDict, Field


class ProviderCreate(BaseModel):
    """Provider creation schema."""

    kind: str
    name: str
    base_url: Optional[str] = None
    credential_ref: Optional[str] = None
    status: str = "active"
    sync_policy_json: Optional[Dict[str, Any]] = None


class ProviderUpdate(BaseModel):
    """Provider update schema."""

    kind: Optional[str] = None
    name: Optional[str] = None
    base_url: Optional[str] = None
    credential_ref: Optional[str] = None
    status: Optional[str] = None
    sync_policy_json: Optional[Dict[str, Any]] = None


class ProviderResponse(BaseModel):
    """Provider response schema."""

    id: str
    kind: str
    name: str
    base_url: Optional[str] = None
    credential_ref: Optional[str] = None
    status: str
    sync_policy_json: Optional[Dict[str, Any]] = None
    last_healthcheck_at: Optional[datetime] = None
    last_healthcheck_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlatformModelResponse(BaseModel):
    """Platform model response schema."""

    id: str
    provider_kind: str
    model_id: str
    display_name: Optional[str] = None
    capabilities_json: Optional[Dict[str, Any]] = None
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    status: str
    lifecycle_status: Optional[str] = None
    lifecycle: Optional[str] = None
    raw_meta: Optional[Dict[str, Any]] = None
    is_active: bool
    last_seen_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProviderModelCreate(BaseModel):
    """Provider model creation schema."""

    model_id: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    capabilities_json: Optional[Dict[str, Any]] = None
    config_json: Optional[Dict[str, Any]] = None
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    lifecycle_status: Optional[str] = None
    lifecycle: Optional[str] = None
    raw_meta: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    enabled: bool = True


class ProviderModelUpdate(BaseModel):
    """Provider model update schema."""

    display_name: Optional[str] = None
    description: Optional[str] = None
    capabilities_json: Optional[Dict[str, Any]] = None
    config_json: Optional[Dict[str, Any]] = None
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    lifecycle_status: Optional[str] = None
    lifecycle: Optional[str] = None
    raw_meta: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    enabled: Optional[bool] = None


class ProviderModelResponse(BaseModel):
    """Provider model response schema."""

    id: str
    provider_id: str
    provider_kind: str
    model_id: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    capabilities_json: Optional[Dict[str, Any]] = None
    config_json: Optional[Dict[str, Any]] = None
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    status: str
    lifecycle_status: Optional[str] = None
    lifecycle: Optional[str] = None
    raw_meta: Optional[Dict[str, Any]] = None
    enabled: bool
    source: str
    platform_model_id: Optional[str] = None
    sync_status: str
    user_overrides_json: Optional[Dict[str, Any]] = None
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SyncFromPlatformRequest(BaseModel):
    """Sync from platform request schema."""

    include_model_ids: Optional[List[str]] = None


class SyncJobResponse(BaseModel):
    """Sync job response schema."""

    id: str
    provider_id: str
    status: str
    diff_json: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HealthcheckResponse(BaseModel):
    """Provider healthcheck response schema."""

    status: str
    message: Optional[str] = None
    checked_at: datetime


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
    response: Optional[str] = None
    latency_ms: Optional[int] = None
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    request_id: Optional[str] = None
