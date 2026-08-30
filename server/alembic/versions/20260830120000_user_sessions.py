"""Add user sessions for refresh and revocation.

Revision ID: 20260830120000
Revises: 20260806160000
Create Date: 2026-08-30 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260830120000"
down_revision: Union[str, Sequence[str], None] = "20260806160000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "user_sessions"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=True),
        # Only the hash is stored: the refresh token is handed to the client
        # once, the same rule API keys follow.
        sa.Column("refresh_token_hash", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(), nullable=True),
    )
    op.create_index(f"ix_{TABLE}_tenant_id", TABLE, ["tenant_id"])
    op.create_index(f"ix_{TABLE}_user_id", TABLE, ["user_id"])
    op.create_index(f"ix_{TABLE}_workspace_id", TABLE, ["workspace_id"])
    op.create_index(
        f"ix_{TABLE}_refresh_token_hash",
        TABLE,
        ["refresh_token_hash"],
        unique=True,
    )
    op.create_index(f"ix_{TABLE}_status", TABLE, ["status"])
    op.create_index(f"ix_{TABLE}_last_seen_at", TABLE, ["last_seen_at"])
    op.create_index(f"ix_{TABLE}_expires_at", TABLE, ["expires_at"])
    op.create_index("ix_user_sessions_user_status", TABLE, ["user_id", "status"])
    op.create_index("ix_user_sessions_expiry", TABLE, ["status", "expires_at"])


def downgrade() -> None:
    op.drop_index("ix_user_sessions_expiry", table_name=TABLE)
    op.drop_index("ix_user_sessions_user_status", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_expires_at", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_last_seen_at", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_status", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_refresh_token_hash", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_workspace_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_user_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_tenant_id", table_name=TABLE)
    op.drop_table(TABLE)
