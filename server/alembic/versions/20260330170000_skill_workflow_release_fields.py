"""Add aligned release metadata fields to skill/workflow publish tables.

Revision ID: 20260330170000_skill_workflow_release_fields
Revises: 20260330143000_drop_agent_mcp_binding_refs
Create Date: 2026-03-30 17:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260330170000_skill_workflow_release_fields"
down_revision = "20260330143000_drop_agent_mcp_binding_refs"
branch_labels = None
depends_on = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in set(_inspector().get_table_names())


def _column_names(table_name: str) -> set[str]:
    if not _has_table(table_name):
        return set()
    return {column["name"] for column in _inspector().get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _has_table(table_name):
        return
    if column.name in _column_names(table_name):
        return
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.add_column(column)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if not _has_table(table_name):
        return
    if column_name not in _column_names(table_name):
        return
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_column(column_name)


def upgrade() -> None:
    for table_name in ("skill_publishes", "workflow_publishes"):
        _add_column_if_missing(table_name, sa.Column("action", sa.String(), nullable=False, server_default="publish"))
        _add_column_if_missing(table_name, sa.Column("from_version_id", sa.String(), nullable=True))
        _add_column_if_missing(table_name, sa.Column("to_version_id", sa.String(), nullable=True))
        _add_column_if_missing(table_name, sa.Column("rollback_of_publish_id", sa.String(), nullable=True))

    _add_column_if_missing("skill_publishes", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    _drop_column_if_exists("skill_publishes", "notes")
    for table_name in ("skill_publishes", "workflow_publishes"):
        _drop_column_if_exists(table_name, "rollback_of_publish_id")
        _drop_column_if_exists(table_name, "to_version_id")
        _drop_column_if_exists(table_name, "from_version_id")
        _drop_column_if_exists(table_name, "action")
