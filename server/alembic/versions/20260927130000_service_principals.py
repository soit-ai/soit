"""Service principals: non-human callers that API keys can be issued to.

Revision ID: 20260927130000
Revises: 20260927120000
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927130000"
down_revision: str | Sequence[str] | None = "20260927120000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "service_principals"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("owner_user_id", sa.String(), nullable=False),
        sa.Column("workspace_role", sa.String(), nullable=False, server_default="Dev"),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "name",
            name="uq_service_principals_scope_name",
        ),
    )
    op.create_index(f"ix_{TABLE}_tenant_id", TABLE, ["tenant_id"])
    op.create_index(f"ix_{TABLE}_workspace_id", TABLE, ["workspace_id"])
    op.create_index(f"ix_{TABLE}_owner_user_id", TABLE, ["owner_user_id"])
    op.add_column("api_keys", sa.Column("principal_id", sa.String(), nullable=True))
    op.create_index("ix_api_keys_principal_id", "api_keys", ["principal_id"])


def downgrade() -> None:
    op.drop_index("ix_api_keys_principal_id", table_name="api_keys")
    op.drop_column("api_keys", "principal_id")
    op.drop_index(f"ix_{TABLE}_owner_user_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_workspace_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_tenant_id", table_name=TABLE)
    op.drop_table(TABLE)
