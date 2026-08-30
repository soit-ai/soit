"""Add the workspace second-factor requirement.

Revision ID: 20260830150000
Revises: 20260830140000
Create Date: 2026-08-30 15:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260830150000"
down_revision: Union[str, Sequence[str], None] = "20260830140000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "workspaces"


def upgrade() -> None:
    # Off for every existing workspace: turning it on locks out members who
    # have not enrolled, which has to be somebody's decision rather than an
    # upgrade's side effect.
    op.add_column(
        TABLE,
        sa.Column(
            "require_mfa",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column(TABLE, "require_mfa")
