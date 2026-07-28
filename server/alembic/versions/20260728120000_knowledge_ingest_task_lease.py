"""Add execution leases to knowledge ingest tasks.

Revision ID: 20260728120000
Revises: 20260726190000
Create Date: 2026-07-28 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260728120000"
down_revision: Union[str, Sequence[str], None] = "20260726190000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "knowledge_ingest_tasks"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("lease_owner", sa.String(), nullable=True))
    op.add_column(
        TABLE,
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        TABLE,
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.create_index(f"ix_{TABLE}_status", TABLE, ["status"])
    op.create_index(f"ix_{TABLE}_lease_owner", TABLE, ["lease_owner"])
    op.create_index(f"ix_{TABLE}_lease_expires_at", TABLE, ["lease_expires_at"])

    # Tasks left running by the pre-lease worker have no owner that can ever
    # finish them. Expiring their lease immediately makes the new claim path
    # reclaim them on the next poll instead of leaving them stuck forever.
    tasks = sa.table(
        TABLE,
        sa.column("status", sa.String()),
        sa.column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.column("attempt_count", sa.Integer()),
    )
    op.get_bind().execute(
        tasks.update()
        .where(tasks.c.status == "running")
        .values(lease_expires_at=sa.func.now(), attempt_count=1)
    )


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_lease_expires_at", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_lease_owner", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_status", table_name=TABLE)
    op.drop_column(TABLE, "attempt_count")
    op.drop_column(TABLE, "lease_expires_at")
    op.drop_column(TABLE, "lease_owner")
