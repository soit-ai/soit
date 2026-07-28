""" schemas

Kernel trace schemas for run/step/artifact/cost.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.kernel.runtime.responses.schemas import ResponseEventRead, ToolCallRead


class RunResponse(BaseModel):
    """Run response schema."""

    id: str
    tenant_id: str
    workspace_id: str
    user_id: str | None
    trace_id: str | None
    request_id: str | None
    parent_run_id: str | None
    source_run_id: str | None
    attempt_no: int
    mode: str
    kind: str | None
    subject_kind: str | None
    subject_id: str | None
    subject_version_id: str | None
    status: str
    input_summary: str | None
    output_summary: str | None
    started_at: datetime
    ended_at: datetime | None
    duration_ms: int | None
    error_code: str | None
    error_message: str | None
    error_step_id: str | None
    created_at: datetime
    updated_at: datetime
    observe_summary: RunObserveSummaryResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class RunStepResponse(BaseModel):
    """Run step response schema."""

    id: str
    run_id: str
    trace_id: str | None
    step_id: str | None
    step_type: str
    node_id: str | None
    status: str
    input_summary: str | None
    output_summary: str | None
    metrics_json: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    error_details: dict[str, Any] | None
    started_at: datetime
    ended_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunStepMetricsSummaryResponse(BaseModel):
    """Aggregated run step metrics summary."""

    step_type: str
    status: str
    count: int
    avg_latency_ms: float | None = None
    min_latency_ms: int | None = None
    max_latency_ms: int | None = None


class RunArtifactResponse(BaseModel):
    """Run artifact response schema."""

    id: str
    run_id: str
    step_id: str | None
    type: str
    storage_key: str
    mime: str | None
    size_bytes: int | None
    sha256: str | None
    meta_json: dict[str, Any] | None
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
    request_count: int = 0
    vector_count: int = 0


class RunChargeSummaryResponse(BaseModel):
    """Aggregated monetary charges grouped by currency."""

    entry_count: int = 0
    amounts: dict[str, Decimal] = Field(default_factory=dict)


class RunCostDailyResponse(BaseModel):
    """Aggregated cost summary by day."""

    date: str
    tokens_prompt: int
    tokens_completion: int
    embedding_count: int
    rerank_count: int
    ms_total: int
    storage_bytes: int
    request_count: int = 0
    vector_count: int = 0


class RunCostBySubjectResponse(BaseModel):
    """Aggregated cost summary by subject version."""

    subject_version_id: str | None
    tokens_prompt: int
    tokens_completion: int
    embedding_count: int
    rerank_count: int
    ms_total: int
    storage_bytes: int
    request_count: int = 0
    vector_count: int = 0


class RunCostByModeResponse(BaseModel):
    """Aggregated cost summary by mode."""

    mode: str
    tokens_prompt: int
    tokens_completion: int
    embedding_count: int
    rerank_count: int
    ms_total: int
    storage_bytes: int
    request_count: int = 0
    vector_count: int = 0


class RunCostByProviderResponse(BaseModel):
    """Aggregated cost summary by provider."""

    provider: str | None
    tokens_prompt: int
    tokens_completion: int
    embedding_count: int
    rerank_count: int
    ms_total: int
    storage_bytes: int
    request_count: int = 0
    vector_count: int = 0


class RunCostByModelResponse(BaseModel):
    """Aggregated cost summary by model."""

    model_ref: str | None
    tokens_prompt: int
    tokens_completion: int
    embedding_count: int
    rerank_count: int
    ms_total: int
    storage_bytes: int
    request_count: int = 0
    vector_count: int = 0


class RunObserveSummaryResponse(BaseModel):
    """Lightweight observability counters for a run."""

    step_count: int = 0
    tool_call_count: int = 0
    child_run_count: int = 0
    response_event_count: int = 0
    citation_count: int = 0
    audit_count: int = 0
    cost_entry_count: int = 0


class RunCostEntryResponse(BaseModel):
    """Normalized usage and cost entry response."""

    id: str
    run_id: str
    step_id: str | None
    tenant_id: str
    workspace_id: str
    currency: str | None
    amount: Decimal | None
    pricing_snapshot_json: dict[str, Any]
    billing_basis: str
    billed_quantity: Decimal
    source_ref: str | None = None
    provider: str | None
    provider_id: str | None
    provider_slug: str | None
    provider_kind: str | None
    model_ref: str | None
    upstream_model: str | None
    tool_ref: str | None
    source_port: str | None = None
    operation: str | None = None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: int | None = None
    request_count: int | None = None
    embedding_count: int | None = None
    rerank_count: int | None = None
    vector_count: int | None = None
    storage_bytes: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunGovernanceEvidenceResponse(BaseModel):
    """Machine-readable governance evidence matrix row."""

    key: str
    status: str
    label: str
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class RunDetailResponse(BaseModel):
    """Run detail response schema."""

    run: RunResponse
    steps: list[RunStepResponse] = Field(default_factory=list)
    artifacts: list[RunArtifactResponse] = Field(default_factory=list)
    usage_summary: RunCostSummaryResponse | None = None
    charge_summary: RunChargeSummaryResponse | None = None
    costs: list[RunCostEntryResponse] = Field(default_factory=list)
    response_events: list[ResponseEventRead] = Field(default_factory=list)
    tool_calls: list[ToolCallRead] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    audits: list[RunAuditLogResponse] = Field(default_factory=list)
    child_runs: list[RunResponse] = Field(default_factory=list)
    governance_evidence: list[RunGovernanceEvidenceResponse] = Field(default_factory=list)


class RunAuditLogResponse(BaseModel):
    """Audit log entry derived from run steps."""

    run_id: str
    step_id: str
    step_type: str
    audit_id: str | None = None
    trace_id: str | None = None
    outcome: str | None = None
    evidence_artifact_id: str | None = None
    gateway_type: str | None = None
    request: dict[str, Any] | None = None
    response: dict[str, Any] | None = None
    timestamp: str | None = None
    truncated: bool = False
    preview: str | None = None
    artifact_key: str | None = None
