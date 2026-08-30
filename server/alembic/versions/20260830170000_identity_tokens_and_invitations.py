"""Add mailed identity links and workspace invitations.

Revision ID: 20260830170000
Revises: 20260830160000
Create Date: 2026-08-30 17:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260830170000"
down_revision: Union[str, Sequence[str], None] = "20260830160000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TOKENS = "identity_tokens"
INVITATIONS = "workspace_invitations"


def upgrade() -> None:
    op.create_table(
        TOKENS,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        # Only the hash: a database dump must not yield a working reset link.
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(f"ix_{TOKENS}_user_id", TOKENS, ["user_id"])
    op.create_index(f"ix_{TOKENS}_purpose", TOKENS, ["purpose"])
    op.create_index(f"ix_{TOKENS}_status", TOKENS, ["status"])
    op.create_index(f"ix_{TOKENS}_expires_at", TOKENS, ["expires_at"])
    op.create_index(f"ix_{TOKENS}_token_hash", TOKENS, ["token_hash"], unique=True)
    op.create_index(
        "ix_identity_tokens_user_purpose",
        TOKENS,
        ["user_id", "purpose", "status"],
    )

    op.create_table(
        INVITATIONS,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("invited_by", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_user_id", sa.String(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(f"ix_{INVITATIONS}_tenant_id", INVITATIONS, ["tenant_id"])
    op.create_index(f"ix_{INVITATIONS}_workspace_id", INVITATIONS, ["workspace_id"])
    op.create_index(f"ix_{INVITATIONS}_email", INVITATIONS, ["email"])
    op.create_index(f"ix_{INVITATIONS}_status", INVITATIONS, ["status"])
    op.create_index(f"ix_{INVITATIONS}_expires_at", INVITATIONS, ["expires_at"])
    op.create_index(
        f"ix_{INVITATIONS}_token_hash",
        INVITATIONS,
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_workspace_invitations_scope",
        INVITATIONS,
        ["workspace_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_workspace_invitations_scope", table_name=INVITATIONS)
    op.drop_index(f"ix_{INVITATIONS}_token_hash", table_name=INVITATIONS)
    op.drop_index(f"ix_{INVITATIONS}_expires_at", table_name=INVITATIONS)
    op.drop_index(f"ix_{INVITATIONS}_status", table_name=INVITATIONS)
    op.drop_index(f"ix_{INVITATIONS}_email", table_name=INVITATIONS)
    op.drop_index(f"ix_{INVITATIONS}_workspace_id", table_name=INVITATIONS)
    op.drop_index(f"ix_{INVITATIONS}_tenant_id", table_name=INVITATIONS)
    op.drop_table(INVITATIONS)

    op.drop_index("ix_identity_tokens_user_purpose", table_name=TOKENS)
    op.drop_index(f"ix_{TOKENS}_token_hash", table_name=TOKENS)
    op.drop_index(f"ix_{TOKENS}_expires_at", table_name=TOKENS)
    op.drop_index(f"ix_{TOKENS}_status", table_name=TOKENS)
    op.drop_index(f"ix_{TOKENS}_purpose", table_name=TOKENS)
    op.drop_index(f"ix_{TOKENS}_user_id", table_name=TOKENS)
    op.drop_table(TOKENS)
