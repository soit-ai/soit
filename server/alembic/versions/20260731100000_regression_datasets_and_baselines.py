"""Give regression cases a versioned dataset and reports a baseline.

Revision ID: 20260731100000
Revises: 20260728240000
Create Date: 2026-07-31 10:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260731100000"
down_revision: Union[str, Sequence[str], None] = "20260728240000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CASES = "regression_cases"
REPORTS = "regression_reports"


def upgrade() -> None:
    # Existing cases were one undifferentiated set; naming it "default" keeps
    # them together rather than inventing a grouping that was never made.
    op.add_column(
        CASES,
        sa.Column("dataset", sa.String(), nullable=False, server_default="default"),
    )
    op.add_column(
        CASES,
        sa.Column("dataset_revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(f"ix_{CASES}_dataset", CASES, ["dataset"])
    op.create_index(f"ix_{CASES}_dataset_revision", CASES, ["dataset_revision"])

    op.add_column(
        REPORTS,
        sa.Column("dataset", sa.String(), nullable=False, server_default="default"),
    )
    op.add_column(
        REPORTS,
        sa.Column("dataset_revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(REPORTS, sa.Column("baseline_report_id", sa.String(), nullable=True))
    op.add_column(
        REPORTS,
        sa.Column(
            "regressed_case_ids_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        REPORTS,
        sa.Column(
            "fixed_case_ids_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.create_index(f"ix_{REPORTS}_dataset", REPORTS, ["dataset"])
    op.create_index(f"ix_{REPORTS}_baseline", REPORTS, ["baseline_report_id"])


def downgrade() -> None:
    op.drop_index(f"ix_{REPORTS}_baseline", table_name=REPORTS)
    op.drop_index(f"ix_{REPORTS}_dataset", table_name=REPORTS)
    op.drop_column(REPORTS, "fixed_case_ids_json")
    op.drop_column(REPORTS, "regressed_case_ids_json")
    op.drop_column(REPORTS, "baseline_report_id")
    op.drop_column(REPORTS, "dataset_revision")
    op.drop_column(REPORTS, "dataset")
    op.drop_index(f"ix_{CASES}_dataset_revision", table_name=CASES)
    op.drop_index(f"ix_{CASES}_dataset", table_name=CASES)
    op.drop_column(CASES, "dataset_revision")
    op.drop_column(CASES, "dataset")
