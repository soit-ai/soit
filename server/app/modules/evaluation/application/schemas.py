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
    source_run_id: str
    name: str
    status: str
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


class RegressionReportResponse(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    subject_kind: str
    subject_id: str
    subject_version_id: str
    passed: bool
    summary_json: dict[str, Any]
    metrics_json: dict[str, Any]
    case_results_json: list[dict[str, Any]]
    created_by: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
