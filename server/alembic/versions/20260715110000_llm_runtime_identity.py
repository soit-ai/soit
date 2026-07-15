"""Add structured LLM runtime identity to cost entries.

Revision ID: 20260715110000
Revises: 20260715100000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260715110000"
down_revision: str | None = "20260715100000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("run_cost_entries", sa.Column("provider_id", sa.String(), nullable=True))
    op.add_column("run_cost_entries", sa.Column("provider_slug", sa.String(), nullable=True))
    op.add_column("run_cost_entries", sa.Column("provider_kind", sa.String(), nullable=True))
    op.add_column("run_cost_entries", sa.Column("upstream_model", sa.String(), nullable=True))
    op.create_index(op.f("ix_run_cost_entries_provider_id"), "run_cost_entries", ["provider_id"])
    op.create_index(
        op.f("ix_run_cost_entries_provider_slug"),
        "run_cost_entries",
        ["provider_slug"],
    )
    op.create_index(
        op.f("ix_run_cost_entries_provider_kind"),
        "run_cost_entries",
        ["provider_kind"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_run_cost_entries_provider_kind"), table_name="run_cost_entries")
    op.drop_index(op.f("ix_run_cost_entries_provider_slug"), table_name="run_cost_entries")
    op.drop_index(op.f("ix_run_cost_entries_provider_id"), table_name="run_cost_entries")
    op.drop_column("run_cost_entries", "upstream_model")
    op.drop_column("run_cost_entries", "provider_kind")
    op.drop_column("run_cost_entries", "provider_slug")
    op.drop_column("run_cost_entries", "provider_id")
