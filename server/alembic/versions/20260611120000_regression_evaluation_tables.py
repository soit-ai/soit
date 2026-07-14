"""add regression evaluation tables

Revision ID: 20260611120000_regression_evaluation_tables
Revises: 20260608110000_provider_model_configuration_json
Create Date: 2026-06-11 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260611120000_regression_evaluation_tables"
down_revision = "20260608110000_provider_model_configuration_json"
branch_labels = None
depends_on = None


def _tables(conn) -> set[str]:
    return set(sa.inspect(conn).get_table_names())


def _indexes(conn, table_name: str) -> set[str]:
    if table_name not in _tables(conn):
        return set()
    return {index["name"] for index in sa.inspect(conn).get_indexes(table_name)}


def _create_index_if_missing(
    conn, table_name: str, name: str, columns: list[str]
) -> None:
    if name not in _indexes(conn, table_name):
        op.create_index(name, table_name, columns)


def _create_regression_cases(conn) -> None:
    if "regression_cases" not in _tables(conn):
        op.create_table(
            "regression_cases",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("subject_kind", sa.String(), nullable=False),
            sa.Column("subject_id", sa.String(), nullable=False),
            sa.Column("subject_version_id", sa.String(), nullable=True),
            sa.Column("source_run_id", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="active"),
            sa.Column("input_snapshot_json", sa.JSON(), nullable=False),
            sa.Column("expected_features_json", sa.JSON(), nullable=False),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    for column_name in (
        "tenant_id",
        "workspace_id",
        "subject_kind",
        "subject_id",
        "subject_version_id",
        "source_run_id",
        "name",
        "status",
    ):
        _create_index_if_missing(
            conn,
            "regression_cases",
            f"ix_regression_cases_{column_name}",
            [column_name],
        )
    _create_index_if_missing(
        conn,
        "regression_cases",
        "ix_regression_cases_subject",
        ["tenant_id", "workspace_id", "subject_kind", "subject_id"],
    )
    _create_index_if_missing(
        conn, "regression_cases", "ix_regression_cases_source_run", ["source_run_id"]
    )


def _create_regression_reports(conn) -> None:
    if "regression_reports" not in _tables(conn):
        op.create_table(
            "regression_reports",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("subject_kind", sa.String(), nullable=False),
            sa.Column("subject_id", sa.String(), nullable=False),
            sa.Column("subject_version_id", sa.String(), nullable=False),
            sa.Column(
                "passed", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column("summary_json", sa.JSON(), nullable=False),
            sa.Column("metrics_json", sa.JSON(), nullable=False),
            sa.Column("case_results_json", sa.JSON(), nullable=False),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    for column_name in (
        "tenant_id",
        "workspace_id",
        "subject_kind",
        "subject_id",
        "subject_version_id",
        "passed",
        "created_at",
    ):
        _create_index_if_missing(
            conn,
            "regression_reports",
            f"ix_regression_reports_{column_name}",
            [column_name],
        )
    _create_index_if_missing(
        conn,
        "regression_reports",
        "ix_regression_reports_subject_version",
        [
            "tenant_id",
            "workspace_id",
            "subject_kind",
            "subject_id",
            "subject_version_id",
        ],
    )
    _create_index_if_missing(
        conn,
        "regression_reports",
        "ix_regression_reports_created",
        ["tenant_id", "workspace_id", "created_at"],
    )


def upgrade() -> None:
    conn = op.get_bind()
    _create_regression_cases(conn)
    _create_regression_reports(conn)


def downgrade() -> None:
    conn = op.get_bind()
    tables = _tables(conn)
    if "regression_reports" in tables:
        op.drop_table("regression_reports")
    if "regression_cases" in tables:
        op.drop_table("regression_cases")
