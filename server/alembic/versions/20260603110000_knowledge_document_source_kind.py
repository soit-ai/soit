"""rename knowledge document source_type to source_kind

Revision ID: 20260603110000_knowledge_document_source_kind
Revises: 20260602170000_database_schema_constraint_convergence
Create Date: 2026-06-03 11:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260603110000_knowledge_document_source_kind"
down_revision = "20260602170000_database_schema_constraint_convergence"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_table("knowledge_documents") or not _has_column(
        "knowledge_documents",
        "source_type",
    ):
        return

    with op.batch_alter_table("knowledge_documents") as batch_op:
        batch_op.alter_column(
            "source_type",
            new_column_name="source_kind",
            existing_type=sa.String(),
            existing_nullable=False,
        )


def downgrade() -> None:
    if not _has_table("knowledge_documents") or not _has_column(
        "knowledge_documents",
        "source_kind",
    ):
        return

    with op.batch_alter_table("knowledge_documents") as batch_op:
        batch_op.alter_column(
            "source_kind",
            new_column_name="source_type",
            existing_type=sa.String(),
            existing_nullable=False,
        )
