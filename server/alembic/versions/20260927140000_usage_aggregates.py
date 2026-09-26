"""Run source and key, and daily usage aggregates.

``runs.source`` records the entry a run came through (existing runs are
``platform``), ``runs.api_key_id`` the key that started it. The new
``usage_daily_aggregates`` table is filled by the ``cost.recorded`` consumer
and rebuilt from ``run_cost_entries`` by the nightly reconciler.

Revision ID: 20260927140000
Revises: 20260927130000
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927140000"
down_revision: str | Sequence[str] | None = "20260927130000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "usage_daily_aggregates"


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("source", sa.String(), nullable=False, server_default="platform"),
    )
    op.add_column("runs", sa.Column("api_key_id", sa.String(), nullable=True))
    op.create_index("ix_runs_source", "runs", ["source"])
    op.create_index("ix_runs_api_key_id", "runs", ["api_key_id"])

    op.create_table(
        TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default=""),
        sa.Column("user_id", sa.String(), nullable=False, server_default=""),
        sa.Column("api_key_id", sa.String(), nullable=False, server_default=""),
        sa.Column("provider_slug", sa.String(), nullable=False, server_default=""),
        sa.Column("model_ref", sa.String(), nullable=False, server_default=""),
        sa.Column("operation", sa.String(), nullable=False, server_default=""),
        sa.Column("currency", sa.String(), nullable=False, server_default=""),
        sa.Column("call_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("prompt_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "day",
            "source",
            "user_id",
            "api_key_id",
            "provider_slug",
            "model_ref",
            "operation",
            "currency",
            name="uq_usage_daily_aggregates_dimensions",
        ),
    )
    op.create_index(
        "ix_usage_daily_aggregates_scope_day", TABLE, ["tenant_id", "workspace_id", "day"]
    )


def downgrade() -> None:
    op.drop_index("ix_usage_daily_aggregates_scope_day", table_name=TABLE)
    op.drop_table(TABLE)
    op.drop_index("ix_runs_api_key_id", table_name="runs")
    op.drop_index("ix_runs_source", table_name="runs")
    op.drop_column("runs", "api_key_id")
    op.drop_column("runs", "source")
