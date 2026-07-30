"""Mark rehearsal runs so their cost and evidence stay separable.

Revision ID: 20260728240000
Revises: 20260728230000
Create Date: 2026-07-28 24:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260728240000"
down_revision: Union[str, Sequence[str], None] = "20260728230000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "runs"


def upgrade() -> None:
    # Existing runs were real work; defaulting them to false is accurate.
    op.add_column(
        TABLE,
        sa.Column(
            "sandbox",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(f"ix_{TABLE}_sandbox", TABLE, ["sandbox"])


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_sandbox", table_name=TABLE)
    op.drop_column(TABLE, "sandbox")
