"""Workspace notification endpoints: team channels for workspace alerts.

Existing endpoints become ``scope = 'user'`` and behave as before.

Revision ID: 20260927160000
Revises: 20260927150000
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927160000"
down_revision: str | Sequence[str] | None = "20260927150000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "notification_endpoints"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("scope", sa.String(length=16), nullable=False, server_default="user"))
    op.add_column(TABLE, sa.Column("categories_json", sa.JSON(), nullable=True))
    op.create_index(f"ix_{TABLE}_scope", TABLE, ["scope"])


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_scope", table_name=TABLE)
    op.drop_column(TABLE, "categories_json")
    op.drop_column(TABLE, "scope")
