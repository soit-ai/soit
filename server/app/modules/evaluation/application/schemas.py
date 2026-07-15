"""Regression evaluation API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

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
