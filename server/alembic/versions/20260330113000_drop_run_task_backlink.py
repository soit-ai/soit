"""Drop run-to-task backlink fields and keep task->run as the only relation.

Revision ID: 20260330113000_drop_run_task_backlink
Revises: 20260329120000_db_constraint_convergence_b7
Create Date: 2026-03-30 11:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260330113000_drop_run_task_backlink"
down_revision = "20260329120000_db_constraint_convergence_b7"
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


def _fk_names_for_column(table_name: str, column_name: str) -> list[str]:
    names: list[str] = []
    for fk in _inspector().get_foreign_keys(table_name):
        constrained = fk.get("constrained_columns") or []
        if column_name in constrained and fk.get("name"):
            names.append(fk["name"])
    return names


def _index_names(table_name: str) -> set[str]:
    return {index["name"] for index in _inspector().get_indexes(table_name) if index.get("name")}


def upgrade() -> None:
    if not _has_table("runs"):
        return

    with op.batch_alter_table("runs") as batch_op:
        if _has_column("runs", "current_task_id"):
            for fk_name in _fk_names_for_column("runs", "current_task_id"):
                batch_op.drop_constraint(fk_name, type_="foreignkey")
            if "ix_runs_current_task_id" in _index_names("runs"):
                batch_op.drop_index("ix_runs_current_task_id")
            batch_op.drop_column("current_task_id")

        if _has_column("runs", "last_error"):
            batch_op.drop_column("last_error")


def downgrade() -> None:
    if not _has_table("runs"):
        return

    with op.batch_alter_table("runs") as batch_op:
        if not _has_column("runs", "current_task_id"):
            batch_op.add_column(sa.Column("current_task_id", sa.String(), nullable=True))
            batch_op.create_index("ix_runs_current_task_id", ["current_task_id"])

        if not _has_column("runs", "last_error"):
            batch_op.add_column(sa.Column("last_error", sa.Text(), nullable=True))
