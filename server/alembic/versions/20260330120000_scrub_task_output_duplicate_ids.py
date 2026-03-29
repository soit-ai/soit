"""Remove duplicate run/thread identifiers from task output payloads.

Revision ID: 20260330120000_scrub_task_output_duplicate_ids
Revises: 20260330113000_drop_run_task_backlink
Create Date: 2026-03-30 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260330120000_scrub_task_output_duplicate_ids"
down_revision = "20260330113000_drop_run_task_backlink"
branch_labels = None
depends_on = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in set(_inspector().get_table_names())


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return column_name in {column["name"] for column in _inspector().get_columns(table_name)}


def upgrade() -> None:
    if not (_has_table("tasks") and _has_column("tasks", "output_json")):
        return
    op.execute(
        sa.text(
            """
            UPDATE tasks
            SET output_json = (
                COALESCE(output_json, '{}'::json)::jsonb
                - 'run_id'
                - 'thread_id'
            )::json
            WHERE output_json IS NOT NULL
              AND (
                output_json::jsonb ? 'run_id'
                OR output_json::jsonb ? 'thread_id'
              )
            """
        )
    )


def downgrade() -> None:
    return None
