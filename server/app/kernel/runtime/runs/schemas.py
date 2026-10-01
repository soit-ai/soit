""" schemas

Kernel trace schemas for run/step/artifact/cost.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

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
    source: str = "platform"
    api_key_id: str | None = None
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
    cost_amount: Decimal | None = None
    """Sum of the run's priced cost entries; None when nothing was priced or
    the entries span more than one currency, which are never added together."""
    cost_currency: str | None = None
    """Currency of ``cost_amount``; None whenever ``cost_amount`` is None."""

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


class RunChargeSummaryResponse(BaseModel):
    """Aggregated monetary charges grouped by currency."""

    entry_count: int = 0
    amounts: dict[str, Decimal] = Field(default_factory=dict)


class RunToolInvocationResponse(BaseModel):
    """How often one tool was invoked inside a window.

    Counted from the cost ledger, which records one entry per governed tool
    invocation. A tool with no entries in the window is simply absent.
    """

    tool_ref: str | None = None
    provider: str | None = None
    invocations: int = 0
    ms_total: int = 0


class RunWindowSummaryResponse(BaseModel):
    """What a workspace did inside one time window.

    Every figure is counted server-side rather than derived from a page of
    runs, so a busy workspace reports the same numbers a quiet one does.
    """

    since: datetime | None = None
    until: datetime | None = None
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    running: int = 0
    pass_rate: float | None = None
    """Succeeded over settled runs. None while nothing has settled, because a
    zero would read as "everything failed"."""

    charges: RunChargeSummaryResponse = Field(default_factory=RunChargeSummaryResponse)


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
    charges: RunChargeSummaryResponse = Field(default_factory=RunChargeSummaryResponse)
    """Money spent under the same filters. Empty when nothing was priced."""


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


CostPricingStatus = Literal["priced", "free", "estimated", "unpriced"]
"""How a cost entry was priced.

``unpriced``: no amount, because no price applied (the reason is in the
pricing snapshot). ``estimated``: an amount computed from usage SOIT estimated
because the provider never reported it (a dropped stream, an unanswered image
call). ``free``: an explicit price of zero. ``priced``: any other amount.
"""

COST_PRICING_STATUSES: tuple[CostPricingStatus, ...] = ("priced", "free", "estimated", "unpriced")


def cost_pricing_status(amount: Decimal | None, snapshot: dict[str, Any] | None) -> CostPricingStatus:
    """The pricing status of one cost entry; mirrors the SQL in ``cost_queries``."""
    if amount is None:
        return "unpriced"
    if (snapshot or {}).get("usage_estimated") is True:
        return "estimated"
    if amount == 0:
        return "free"
    return "priced"


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
    upstream_id: str | None = None
    upstream_request_id: str | None = None
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
    api_key_id: str | None = None
    """The run's API key. Set on ``/runs/costs/entries``; None elsewhere."""
    user_id: str | None = None
    """The run's member or service principal. Set on ``/runs/costs/entries``."""
    run_source: str | None = None
    """The run's source (``platform`` or ``gateway``). Set on ``/runs/costs/entries``."""

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def pricing_status(self) -> CostPricingStatus:
        return cost_pricing_status(self.amount, self.pricing_snapshot_json)

    @computed_field
    @property
    def unpriced_reason(self) -> str | None:
        """Why no price applied, from the pricing snapshot; None when priced."""
        if self.amount is not None:
            return None
        reason = (self.pricing_snapshot_json or {}).get("reason")
        return str(reason) if reason else "unknown"


CostGroupBy = Literal["model", "provider", "tool", "api_key", "user", "source", "operation", "day"]


class CostReconciliationGroupResponse(BaseModel):
    """Cost entries sharing one value of the grouping dimension and one currency.

    Unpriced entries have no currency, so they form their own row per key.
    """

    key: str | None
    currency: str | None
    entry_count: int
    amount: Decimal | None
    """Sum of the priced amounts; None for the row of unpriced entries."""
    estimated_count: int = 0
    unpriced_count: int = 0
    total_tokens: int = 0


class CostUnpricedReasonResponse(BaseModel):
    reason: str
    entry_count: int


class CostReconciliationResponse(BaseModel):
    """What the ledger recorded in a window, ready to be checked against a bill.

    Amounts are kept per currency and never added across currencies. The
    window is half-open, ``[since, until)``, like the ledger exports, so
    adjacent windows never count an entry twice.
    """

    since: datetime | None
    until: datetime | None
    entry_count: int
    status_counts: dict[str, int]
    """Entries per pricing status: priced, free, estimated, unpriced."""
    amounts: dict[str, Decimal] = Field(default_factory=dict)
    """Priced total per currency, estimated amounts included."""
    estimated_amounts: dict[str, Decimal] = Field(default_factory=dict)
    """The part of ``amounts`` computed from estimated usage."""
    unpriced_reasons: list[CostUnpricedReasonResponse] = Field(default_factory=list)
    group_by: CostGroupBy | None = None
    groups: list[CostReconciliationGroupResponse] = Field(default_factory=list)
    groups_truncated: bool = False
    external_reconciliation: Literal["not_performed"] = "not_performed"
    """Whether these figures were matched against a provider's bill. Always
    ``not_performed`` here: this is the ledger's side only."""


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
    # Who did it and to what. The gateway is how the call was made, not who
    # made it, and the run is where it happened, not what it touched.
    actor_user_id: str | None = None
    operation: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    created_at: datetime | None = None
