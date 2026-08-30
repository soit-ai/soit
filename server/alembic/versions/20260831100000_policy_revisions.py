"""Add policy revisions.

Revision ID: 20260831100000
Revises: 20260830180000
Create Date: 2026-08-31 10:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260831100000"
down_revision: Union[str, Sequence[str], None] = "20260830180000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "policy_revisions"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("scope_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("bundle_id", sa.String(), nullable=False),
        sa.Column("document_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("restored_from_revision", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "scope",
            "scope_id",
            "revision",
            name="uq_policy_revisions_scope_revision",
        ),
    )
    op.create_index(f"ix_{TABLE}_tenant_id", TABLE, ["tenant_id"])
    op.create_index(f"ix_{TABLE}_workspace_id", TABLE, ["workspace_id"])
    op.create_index(f"ix_{TABLE}_bundle_id", TABLE, ["bundle_id"])
    op.create_index(f"ix_{TABLE}_created_at", TABLE, ["created_at"])
    op.create_index("ix_policy_revisions_scope", TABLE, ["tenant_id", "scope", "scope_id", "revision"])


def downgrade() -> None:
    op.drop_index("ix_policy_revisions_scope", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_created_at", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_bundle_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_workspace_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_tenant_id", table_name=TABLE)
    op.drop_table(TABLE)
