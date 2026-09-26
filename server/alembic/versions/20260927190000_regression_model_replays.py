"""Regression model replays: regression sets replayed on another model.

``regression_model_replays`` keeps each replay's comparison of an agent's
current model with a candidate model: pass rate, latency and cost on both
sides, per agent and dataset. It is a new table; nothing existing changes.

Revision ID: 20260927190000
Revises: 20260927180000
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927190000"
down_revision: str | Sequence[str] | None = "20260927180000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "regression_model_replays"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("model_ref", sa.String(), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subjects_json", sa.JSON(), nullable=True),
        sa.Column("totals_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(f"ix_{TABLE}_tenant_id", TABLE, ["tenant_id"])
    op.create_index(f"ix_{TABLE}_workspace_id", TABLE, ["workspace_id"])
    op.create_index(f"ix_{TABLE}_model_ref", TABLE, ["model_ref"])
    op.create_index(f"ix_{TABLE}_created", TABLE, ["tenant_id", "workspace_id", "created_at"])


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_created", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_model_ref", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_workspace_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_tenant_id", table_name=TABLE)
    op.drop_table(TABLE)
