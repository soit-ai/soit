"""Narrow run_cost_entries billing semantics and add idempotency key.

``unit``/``quantity`` become ``billing_basis``/``billed_quantity``: they
only describe what the row is billed by, never feed usage statistics
(dedicated dimension columns do). Database-level CHECK constraints encode
the pricing invariants that previously lived only in the writer, and an
optional ``source_ref`` upstream identifier gains a unique key so retried
invocations cannot double-book.

Revision ID: 20260728160000
Revises: 20260728150000
Create Date: 2026-07-28 16:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260728160000"
down_revision: Union[str, Sequence[str], None] = "20260728150000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("run_cost_entries") as batch_op:
        batch_op.alter_column(
            "unit",
            new_column_name="billing_basis",
            existing_type=sa.String(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "quantity",
            new_column_name="billed_quantity",
            existing_type=sa.Numeric(18, 6),
            existing_nullable=False,
        )
        batch_op.add_column(sa.Column("source_ref", sa.String(), nullable=True))

    with op.batch_alter_table("run_cost_entries") as batch_op:
        batch_op.create_check_constraint(
            "ck_run_cost_entries_priced_amount",
            "amount IS NULL OR (amount >= 0 AND currency IS NOT NULL)",
        )
        batch_op.create_check_constraint(
            "ck_run_cost_entries_billed_quantity_non_negative",
            "billed_quantity >= 0",
        )

    op.create_index(
        "uq_run_cost_entries_tenant_source_ref",
        "run_cost_entries",
        ["tenant_id", "source_ref"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_run_cost_entries_tenant_source_ref", table_name="run_cost_entries"
    )
    with op.batch_alter_table("run_cost_entries") as batch_op:
        batch_op.drop_constraint(
            "ck_run_cost_entries_billed_quantity_non_negative", type_="check"
        )
        batch_op.drop_constraint(
            "ck_run_cost_entries_priced_amount", type_="check"
        )
    with op.batch_alter_table("run_cost_entries") as batch_op:
        batch_op.drop_column("source_ref")
        batch_op.alter_column(
            "billed_quantity",
            new_column_name="quantity",
            existing_type=sa.Numeric(18, 6),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "billing_basis",
            new_column_name="unit",
            existing_type=sa.String(),
            existing_nullable=False,
        )
