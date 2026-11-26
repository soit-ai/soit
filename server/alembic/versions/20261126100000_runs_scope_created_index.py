"""Index runs by workspace and creation time.

The runs list, the console's busiest query, filters on tenant and workspace
and orders by ``created_at``; no index covered that, so every page sorted the
workspace's runs. On PostgreSQL the index is built concurrently so a large
``runs`` table stays writable while it builds.

Revision ID: 20261126100000
Revises: 20261003110000
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20261126100000"
down_revision: str | Sequence[str] | None = "20261003110000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX = "ix_runs_scope_created"
COLUMNS = ["tenant_id", "workspace_id", "created_at"]


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.create_index(INDEX, "runs", COLUMNS, postgresql_concurrently=True, if_not_exists=True)
    else:
        op.create_index(INDEX, "runs", COLUMNS)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.drop_index(INDEX, table_name="runs", postgresql_concurrently=True, if_exists=True)
    else:
        op.drop_index(INDEX, table_name="runs")
