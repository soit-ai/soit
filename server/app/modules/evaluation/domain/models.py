"""Regression evaluation persistence models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Index
from sqlmodel import JSON, Column, Field, SQLModel

from app.kernel.commons.ids import generate_ulid
from app.kernel.commons.time import utc_now


def generate_regression_case_id() -> str:
    return f"regcase_{generate_ulid()}"


def generate_regression_report_id() -> str:
    return f"regrep_{generate_ulid()}"


class RegressionCase(SQLModel, table=True):
    """Frozen historical run input and expected behavior."""

    __tablename__ = "regression_cases"
    __table_args__ = (
        Index(
            "ix_regression_cases_subject",
            "tenant_id",
            "workspace_id",
            "subject_kind",
            "subject_id",
        ),
        Index("ix_regression_cases_source_run", "source_run_id"),
    )

    id: str = Field(primary_key=True, default_factory=generate_regression_case_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    subject_kind: str = Field(index=True)
    subject_id: str = Field(index=True)
    subject_version_id: str | None = Field(default=None, nullable=True, index=True)
    source_run_id: str = Field(index=True)
    name: str = Field(index=True)
    status: str = Field(default="active", index=True)
    input_snapshot_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )
    expected_features_json: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )
    created_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now)


class RegressionReport(SQLModel, table=True):
    """Batch regression report for a subject version."""

    __tablename__ = "regression_reports"
    __table_args__ = (
        Index(
            "ix_regression_reports_subject_version",
            "tenant_id",
            "workspace_id",
            "subject_kind",
            "subject_id",
            "subject_version_id",
        ),
        Index(
            "ix_regression_reports_created", "tenant_id", "workspace_id", "created_at"
        ),
    )

    id: str = Field(primary_key=True, default_factory=generate_regression_report_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    subject_kind: str = Field(index=True)
    subject_id: str = Field(index=True)
    subject_version_id: str = Field(index=True)
    passed: bool = Field(default=False, index=True)
    summary_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    metrics_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    case_results_json: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    created_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
