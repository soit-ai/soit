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


def generate_regression_annotation_id() -> str:
    return f"regann_{generate_ulid()}"


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
    dataset: str = Field(default="default", index=True)
    """Named set this case belongs to, so unrelated suites stay separable."""

    dataset_revision: int = Field(default=1, index=True)
    """Bumped whenever the set's membership changes.

    Two reports are only comparable if they ran the same cases; without a
    revision, a report that silently gained or lost cases would look like a
    quality change.
    """
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
    dataset: str = Field(default="default", index=True)
    dataset_revision: int = Field(default=1)
    """Which set, at which revision, this report actually ran."""

    baseline_report_id: str | None = Field(default=None, nullable=True, index=True)
    """The report this one was compared against, if any."""

    regressed_case_ids_json: list[str] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    """Cases that passed in the baseline and fail here.

    Kept apart from failures generally: a case that never passed is a known
    gap, while one that used to pass is something this change broke.
    """

    fixed_case_ids_json: list[str] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    summary_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    metrics_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    case_results_json: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    created_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class RegressionAnnotation(SQLModel, table=True):
    """Human verdict on one case, optionally tied to one report's run of it.

    Annotations never change the automated result; they are review evidence
    that sits next to it, so a disagreement stays visible instead of being
    overwritten.
    """

    __tablename__ = "regression_annotations"
    __table_args__ = (
        Index(
            "ix_regression_annotations_case",
            "tenant_id",
            "workspace_id",
            "case_id",
        ),
        Index("ix_regression_annotations_report", "report_id"),
    )

    id: str = Field(primary_key=True, default_factory=generate_regression_annotation_id)
    tenant_id: str = Field(index=True)
    workspace_id: str = Field(index=True)
    case_id: str = Field(index=True)
    report_id: str | None = Field(default=None, nullable=True)
    verdict: str = Field(index=True)
    """Human judgment: "pass" or "fail"."""

    note: str = Field(default="")
    annotated_by: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
