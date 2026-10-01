"""Regression evaluation API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RegressionCaseCreateFromRun(BaseModel):
    run_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=255)
    expected_features: dict[str, Any] = Field(default_factory=dict)


class RegressionCaseResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    subject_kind: str
    subject_id: str
    subject_version_id: str | None
    source_run_id: str | None
    name: str
    status: str
    dataset: str
    dataset_revision: int
    input_snapshot_json: dict[str, Any]
    expected_features_json: dict[str, Any]
    created_by: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RegressionAnnotationCreate(BaseModel):
    case_id: str = Field(..., min_length=1)
    report_id: str | None = None
    verdict: Literal["pass", "fail"]
    note: str = Field(default="", max_length=4000)


class RegressionAnnotationResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    case_id: str
    report_id: str | None
    verdict: str
    note: str
    annotated_by: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RegressionTrendPoint(BaseModel):
    report_id: str
    subject_version_id: str
    dataset: str
    dataset_revision: int
    created_at: datetime
    passed: bool
    total: int
    passed_count: int
    pass_rate: float | None
    regressed: int
    fixed: int
    avg_latency_ms: int | None
    total_cost_amount: float | None


class RegressionTrendResponse(BaseModel):
    subject_kind: str
    subject_id: str
    dataset: str | None
    points: list[RegressionTrendPoint]


class RegressionReportSummaryResponse(BaseModel):
    """A report without its per-case results, for lists."""

    id: str
    tenant_id: str
    workspace_id: str
    subject_kind: str
    subject_id: str
    subject_version_id: str
    passed: bool
    dataset: str
    dataset_revision: int
    baseline_report_id: str | None
    regressed_case_ids_json: list[str]
    fixed_case_ids_json: list[str]
    summary_json: dict[str, Any]
    metrics_json: dict[str, Any]
    created_by: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RegressionReportResponse(RegressionReportSummaryResponse):
    case_results_json: list[dict[str, Any]]


class EvaluationRunCreate(BaseModel):
    """Run a subject version's regression set now."""

    model_config = ConfigDict(extra="forbid")

    subject_kind: Literal["agent"] = "agent"
    subject_id: str = Field(..., min_length=1, max_length=255)
    subject_version_id: str | None = Field(
        default=None, max_length=255, description="The version to run; the published one when omitted"
    )
    dataset: str = Field(default="default", min_length=1, max_length=255)
    model_ref: str | None = Field(
        default=None,
        max_length=512,
        description="Run the cases on this model instead of the version's own; the report is then no baseline",
    )
    max_cases: int = Field(default=50, ge=1, le=200, description="Refuse an evaluation that would run more cases")


class ModelReplayCreate(BaseModel):
    """Replay regression sets on a candidate model."""

    model_config = ConfigDict(extra="forbid")

    model_ref: str = Field(..., min_length=1, max_length=512)
    agent_ids: list[str] | None = Field(
        default=None,
        max_length=100,
        description="Agents to replay; every agent with regression cases when omitted",
    )
    dataset: str | None = Field(default=None, max_length=255, description="One dataset; every dataset when omitted")
    max_cases: int = Field(default=50, ge=1, le=200, description="Refuse a replay that would run more cases")


class ModelReplaySummaryResponse(BaseModel):
    id: str
    model_ref: str
    case_count: int
    totals: dict[str, Any] = Field(validation_alias="totals_json")
    created_by: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelReplayResponse(ModelReplaySummaryResponse):
    subjects: list[dict[str, Any]] = Field(validation_alias="subjects_json")


class DatasetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_kind: Literal["agent"] = "agent"
    subject_id: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)


class DatasetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = Field(default=None, max_length=2000)
    status: Literal["active", "archived"] | None = None


class DatasetLatestReport(BaseModel):
    id: str
    passed: bool
    total: int
    passed_count: int
    pass_rate: float | None
    dataset_revision: int
    subject_version_id: str
    model_ref: str | None
    created_at: datetime


class DatasetResponse(BaseModel):
    id: str
    subject_kind: str
    subject_id: str
    name: str
    description: str
    revision: int
    status: str
    case_count: int
    latest_report: DatasetLatestReport | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class DatasetCaseCreate(BaseModel):
    """One case in the dataset case format (``dataset_case_spec``)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    input: str | dict[str, Any]
    expected_features: dict[str, Any]
    note: str = Field(default="", max_length=500)


class DatasetCaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    input: str | dict[str, Any] | None = None
    expected_features: dict[str, Any] | None = None
    note: str = Field(default="", max_length=500)


class DatasetCaseResponse(RegressionCaseResponse):
    """A case with its input in the dataset case format."""

    input: str | dict[str, Any]


class DatasetImport(BaseModel):
    """A JSONL file's text: one case per line, validated all or nothing."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(..., min_length=1)
    note: str = Field(default="", max_length=500)


class DatasetImportResponse(BaseModel):
    imported: int
    dataset: DatasetResponse


class DatasetVersionResponse(BaseModel):
    id: str
    dataset_id: str
    revision: int
    case_count: int
    content_hash: str
    changes: dict[str, int] = Field(validation_alias="changes_json")
    note: str
    created_by: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DatasetVersionDetailResponse(DatasetVersionResponse):
    snapshot: list[dict[str, Any]] = Field(validation_alias="snapshot_json")
