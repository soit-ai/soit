"""Add second-factor enrolments.

Revision ID: 20260830140000
Revises: 20260830130000
Create Date: 2026-08-30 14:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260830140000"
down_revision: Union[str, Sequence[str], None] = "20260830130000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "user_mfa"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        # Sealed, not hashed: the secret has to be readable to recompute codes.
        sa.Column("secret_sealed", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column(
            "recovery_hashes_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_user_mfa_user"),
    )
    op.create_index(f"ix_{TABLE}_user_id", TABLE, ["user_id"])
    op.create_index(f"ix_{TABLE}_status", TABLE, ["status"])


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_status", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_user_id", table_name=TABLE)
    op.drop_table(TABLE)
