"""Add draft review state to agent versions.

Revision ID: 20260831110000
Revises: 20260831100000
Create Date: 2026-08-31 11:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260831110000"
down_revision: Union[str, Sequence[str], None] = "20260831100000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "agent_versions"


def upgrade() -> None:
    # Existing drafts are "none": nobody was asked to look at them, and
    # backfilling them into a review queue would invent a queue.
    op.add_column(
        TABLE,
        sa.Column("review_status", sa.String(), nullable=False, server_default="none"),
    )
    op.add_column(TABLE, sa.Column("review_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(TABLE, sa.Column("review_requested_by", sa.String(), nullable=True))
    op.add_column(TABLE, sa.Column("review_note", sa.String(), nullable=True))
    op.add_column(TABLE, sa.Column("reviewed_by", sa.String(), nullable=True))
    op.add_column(TABLE, sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(f"ix_{TABLE}_review_status", TABLE, ["review_status"])


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_review_status", table_name=TABLE)
    op.drop_column(TABLE, "reviewed_at")
    op.drop_column(TABLE, "reviewed_by")
    op.drop_column(TABLE, "review_note")
    op.drop_column(TABLE, "review_requested_by")
    op.drop_column(TABLE, "review_requested_at")
    op.drop_column(TABLE, "review_status")
