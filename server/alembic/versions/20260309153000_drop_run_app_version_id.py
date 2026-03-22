"""Drop the retired runs.app_version_id column.

Revision ID: 20260309153000_drop_run_app_version_id
Revises: 20260309120000_squash_runtime_knowledge_refactor
Create Date: 2026-03-09 15:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260309153000_drop_run_app_version_id"
down_revision = "20260309120000_squash_runtime_knowledge_refactor"
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


def _index_names(table_name: str) -> set[str]:
    if not _has_table(table_name):
        return set()
    return {index["name"] for index in _inspector().get_indexes(table_name)}


def upgrade() -> None:
    if not _has_table("runs"):
        return

    columns = _column_names("runs")
    if "app_version_id" not in columns:
        return

    if "subject_version_id" in columns:
        op.execute(
            sa.text(
                """
                UPDATE runs
                SET subject_version_id = COALESCE(subject_version_id, app_version_id)
                WHERE app_version_id IS NOT NULL
                """
            )
        )

    indexes = _index_names("runs")
    for index_name in ("ix_runs_app_version_id",):
        if index_name in indexes:
            op.drop_index(index_name, table_name="runs")

    op.drop_column("runs", "app_version_id")


def downgrade() -> None:
    if not _has_table("runs"):
        return

    columns = _column_names("runs")
    if "app_version_id" in columns:
        return

    op.add_column("runs", sa.Column("app_version_id", sa.String(), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE runs
            SET app_version_id = subject_version_id
            WHERE subject_version_id IS NOT NULL
            """
        )
    )
