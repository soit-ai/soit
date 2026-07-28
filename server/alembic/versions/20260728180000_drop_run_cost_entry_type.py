"""Drop run_cost_entries.entry_type.

The usage/charge split is fully retired: the 20260726190000 migration
merged or converted every historical charge row, and the writer has only
accepted usage rows since. The column is now a constant and only invites
consumers to filter on it, so it goes away.

Revision ID: 20260728180000
Revises: 20260728160000
Create Date: 2026-07-28 18:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260728180000"
down_revision: Union[str, Sequence[str], None] = "20260728160000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(
        op.f("ix_run_cost_entries_entry_type"), table_name="run_cost_entries"
    )
    with op.batch_alter_table("run_cost_entries") as batch_op:
        batch_op.drop_column("entry_type")


def downgrade() -> None:
    with op.batch_alter_table("run_cost_entries") as batch_op:
        batch_op.add_column(
            sa.Column(
                "entry_type",
                sa.String(),
                nullable=False,
                server_default="usage",
            )
        )
    op.create_index(
        op.f("ix_run_cost_entries_entry_type"),
        "run_cost_entries",
        ["entry_type"],
    )
