"""add last run id to knowledge indexes

Revision ID: 20260607100000_knowledge_index_last_run_id
Revises: 20260604120000_table_convergence
Create Date: 2026-06-07 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260607100000_knowledge_index_last_run_id"
down_revision = "20260604120000_table_convergence"
branch_labels = None
depends_on = None


def _columns(conn, table_name: str) -> set[str]:
    if table_name not in sa.inspect(conn).get_table_names():
        return set()
    return {column["name"] for column in sa.inspect(conn).get_columns(table_name)}


def upgrade() -> None:
    conn = op.get_bind()
    if "last_run_id" not in _columns(conn, "knowledge_indexes"):
        op.add_column("knowledge_indexes", sa.Column("last_run_id", sa.String(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if "last_run_id" in _columns(conn, "knowledge_indexes"):
        op.drop_column("knowledge_indexes", "last_run_id")
