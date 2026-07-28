"""Create credit_ledger_entries.

Credit deduction is a derived valuation over priced usage rows: each
deduction references its run_cost_entries row via a unique cost_entry_id,
so replayed COST_RECORDED events cannot double-book, and measured usage
is never copied into the ledger.

Revision ID: 20260728200000
Revises: 20260728180000
Create Date: 2026-07-28 20:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260728200000"
down_revision: Union[str, Sequence[str], None] = "20260728180000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "credit_ledger_entries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("credits_delta", sa.Numeric(18, 6), nullable=False),
        sa.Column("cost_entry_id", sa.String(), nullable=True),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("amount", sa.Numeric(18, 6), nullable=True),
        sa.Column("conversion_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(kind = 'deduction' AND credits_delta <= 0)"
            " OR (kind = 'grant' AND credits_delta >= 0)"
            " OR kind = 'adjustment'",
            name="ck_credit_ledger_kind_sign",
        ),
        sa.CheckConstraint(
            "kind <> 'deduction' OR cost_entry_id IS NOT NULL",
            name="ck_credit_ledger_deduction_has_cost_entry",
        ),
    )
    op.create_index(
        "uq_credit_ledger_cost_entry",
        "credit_ledger_entries",
        ["cost_entry_id"],
        unique=True,
    )
    op.create_index(
        "ix_credit_ledger_scope_created",
        "credit_ledger_entries",
        ["tenant_id", "workspace_id", "created_at"],
    )
    op.create_index(
        op.f("ix_credit_ledger_entries_tenant_id"),
        "credit_ledger_entries",
        ["tenant_id"],
    )
    op.create_index(
        op.f("ix_credit_ledger_entries_workspace_id"),
        "credit_ledger_entries",
        ["workspace_id"],
    )
    op.create_index(
        op.f("ix_credit_ledger_entries_run_id"),
        "credit_ledger_entries",
        ["run_id"],
    )
    op.create_index(
        op.f("ix_credit_ledger_entries_created_at"),
        "credit_ledger_entries",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("credit_ledger_entries")
