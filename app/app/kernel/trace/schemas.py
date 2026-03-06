""" schemas

Kernel trace schemas for run/step/artifact/cost.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class RunResponse(BaseModel):
    """Run response schema."""

    id: str
    tenant_id: str
    workspace_id: str
    user_id: Optional[str]
    trace_id: Optional[str]
    mode: str
    kind: Optional[str]
    app_id: str
    app_version_id: str
    app_type: Optional[str]
    status: str
    input_summary: Optional[str]
    output_summary: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    duration_ms: Optional[int]
    error_code: Optional[str]
    error_message: Optional[str]
    error_step_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunStepResponse(BaseModel):
    """Run step response schema."""

    id: str
    run_id: str
    trace_id: Optional[str]
    step_id: Optional[str]
    step_type: str
    node_id: Optional[str]
    status: str
    input_summary: Optional[str]
    output_summary: Optional[str]
    metrics_json: Optional[Dict[str, Any]]
    error_code: Optional[str]
    error_message: Optional[str]
    error_details: Optional[Dict[str, Any]]
    started_at: datetime
    ended_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunStepMetricsSummaryResponse(BaseModel):
    """Aggregated run step metrics summary."""

    step_type: str
    status: str
    count: int
    avg_latency_ms: Optional[float] = None
    min_latency_ms: Optional[int] = None
    max_latency_ms: Optional[int] = None


class RunArtifactResponse(BaseModel):
    """Run artifact response schema."""

    id: str
    run_id: str
    step_id: Optional[str]
    type: str
    storage_key: str
    mime: Optional[str]
    size_bytes: Optional[int]
    sha256: Optional[str]
    meta_json: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunCostSummaryResponse(BaseModel):
    """Aggregated cost summary."""

    tokens_prompt: int
    tokens_completion: int
    embedding_count: int
    rerank_count: int
    ms_total: int
    storage_bytes: int


class RunCostDailyResponse(BaseModel):
    """Aggregated cost summary by day."""

    date: str
    tokens_prompt: int
    tokens_completion: int
    embedding_count: int
    rerank_count: int
    ms_total: int
    storage_bytes: int


class RunCostByAppResponse(BaseModel):
    """Aggregated cost summary by app version."""

    app_version_id: Optional[str]
    tokens_prompt: int
    tokens_completion: int
    embedding_count: int
    rerank_count: int
    ms_total: int
    storage_bytes: int


class RunCostByModeResponse(BaseModel):
    """Aggregated cost summary by mode."""

    mode: str
    tokens_prompt: int
    tokens_completion: int
    embedding_count: int
    rerank_count: int
    ms_total: int
    storage_bytes: int


class RunCostByProviderResponse(BaseModel):
    """Aggregated cost summary by provider."""

    provider: Optional[str]
    tokens_prompt: int
    tokens_completion: int
    embedding_count: int
    rerank_count: int
    ms_total: int
    storage_bytes: int


class RunCostByModelResponse(BaseModel):
    """Aggregated cost summary by model."""

    model_ref: Optional[str]
    tokens_prompt: int
    tokens_completion: int
    embedding_count: int
    rerank_count: int
    ms_total: int
    storage_bytes: int


class RunCostEntryResponse(BaseModel):
    """Normalized cost entry response."""

    id: str
    run_id: str
    step_id: Optional[str]
    tenant_id: str
    workspace_id: str
    currency: str
    amount: Decimal
    unit: str
    quantity: Decimal
    provider: Optional[str]
    model_ref: Optional[str]
    tool_ref: Optional[str]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunDetailResponse(BaseModel):
    """Run detail response schema."""

    run: RunResponse
    steps: List[RunStepResponse]
    artifacts: List[RunArtifactResponse]
    cost_summary: Optional[RunCostSummaryResponse] = None
    costs: Optional[List[RunCostEntryResponse]] = None


class RunAuditLogResponse(BaseModel):
    """Audit log entry derived from run steps."""

    run_id: str
    step_id: str
    step_type: str
    gateway_type: Optional[str] = None
    request: Optional[Dict[str, Any]] = None
    response: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    truncated: bool = False
    preview: Optional[str] = None
    artifact_key: Optional[str] = None
