"""Add execution leases and input snapshots to workflow runs.

Revision ID: 20260728220000
Revises: 20260728200000
Create Date: 2026-07-28 22:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260728220000"
down_revision: Union[str, Sequence[str], None] = "20260728200000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "workflow_runs"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column("inputs_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        TABLE,
        sa.Column(
            "request_context_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(TABLE, sa.Column("lease_owner", sa.String(), nullable=True))
    op.add_column(
        TABLE,
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        TABLE,
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    op.create_index(f"ix_{TABLE}_lease_owner", TABLE, ["lease_owner"])
    op.create_index(f"ix_{TABLE}_lease_expires_at", TABLE, ["lease_expires_at"])

    # Runs left running by the pre-lease in-request executor have no owner that
    # can finish them. Expiring their lease immediately lets the claim path
    # reclaim them instead of leaving them stuck.
    runs = sa.table(
        TABLE,
        sa.column("status", sa.String()),
        sa.column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.column("attempt_count", sa.Integer()),
    )
    op.get_bind().execute(
        runs.update()
        .where(runs.c.status == "running")
        .values(lease_expires_at=sa.func.now(), attempt_count=1)
    )


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_lease_expires_at", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_lease_owner", table_name=TABLE)
    op.drop_column(TABLE, "attempt_count")
    op.drop_column(TABLE, "lease_expires_at")
    op.drop_column(TABLE, "lease_owner")
    op.drop_column(TABLE, "request_context_json")
    op.drop_column(TABLE, "inputs_json")
