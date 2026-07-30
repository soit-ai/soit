"""Add scopes and expiry to API keys.

Revision ID: 20260728230000
Revises: 20260728220000
Create Date: 2026-07-28 23:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260728230000"
down_revision: Union[str, Sequence[str], None] = "20260728220000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "api_keys"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column("scopes_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(TABLE, sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(f"ix_{TABLE}_expires_at", TABLE, ["expires_at"])

    # Keys issued before scopes existed inherited the user's full role. Leaving
    # them unscoped would silently keep that authority, so revoke them: an
    # operator must reissue with an explicit scope and expiry. Access this
    # broad must be granted deliberately, not grandfathered.
    keys = sa.table(
        TABLE,
        sa.column("status", sa.String()),
        sa.column("revoked_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    op.get_bind().execute(
        keys.update()
        .where(keys.c.status == "active")
        .values(status="revoked", revoked_at=sa.func.now(), updated_at=sa.func.now())
    )


def downgrade() -> None:
    op.drop_index(f"ix_{TABLE}_expires_at", table_name=TABLE)
    op.drop_column(TABLE, "expires_at")
    op.drop_column(TABLE, "scopes_json")
