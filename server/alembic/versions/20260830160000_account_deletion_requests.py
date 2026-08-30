"""Add account closure requests.

Revision ID: 20260830160000
Revises: 20260830150000
Create Date: 2026-08-30 16:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260830160000"
down_revision: Union[str, Sequence[str], None] = "20260830150000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "account_deletion_requests"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("reason", sa.String(length=512), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        # The pause. Until it elapses the request can be withdrawn, which is
        # the whole point of recording one rather than closing immediately.
        sa.Column("execute_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(f"ix_{TABLE}_user_id", TABLE, ["user_id"])
    op.create_index(f"ix_{TABLE}_tenant_id", TABLE, ["tenant_id"])
    op.create_index(f"ix_{TABLE}_status", TABLE, ["status"])
    op.create_index(f"ix_{TABLE}_execute_after", TABLE, ["execute_after"])
    op.create_index(
        "ix_account_deletion_requests_due",
        TABLE,
        ["status", "execute_after"],
    )


def downgrade() -> None:
    op.drop_index("ix_account_deletion_requests_due", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_execute_after", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_status", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_tenant_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_user_id", table_name=TABLE)
    op.drop_table(TABLE)
