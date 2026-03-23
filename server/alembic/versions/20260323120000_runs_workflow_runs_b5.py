"""B5: runs headline fields + workflow_runs aggregate table.

Revision ID: 20260323120000_runs_workflow_runs_b5
Revises: 20260323100000_event_outbox_tables
Create Date: 2026-03-23 12:00:00

Backfill: new columns are nullable; RuntimeCoreService updates current_task_id / last_error
on task transitions. Existing rows stay NULL until the next matching task update.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260323120000_runs_workflow_runs_b5"
down_revision = "20260323100000_event_outbox_tables"
branch_labels = None
depends_on = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in set(_inspector().get_table_names())


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return column_name in {c["name"] for c in _inspector().get_columns(table_name)}


def upgrade() -> None:
    if _has_table("runs"):
        if not _has_column("runs", "current_task_id"):
            with op.batch_alter_table("runs") as batch:
                batch.add_column(sa.Column("current_task_id", sa.String(), nullable=True))
                batch.create_foreign_key(
                    "fk_runs_current_task_id_tasks",
                    "tasks",
                    ["current_task_id"],
                    ["id"],
                )
                batch.create_index("ix_runs_current_task_id", ["current_task_id"])
        if not _has_column("runs", "last_error"):
            op.add_column("runs", sa.Column("last_error", sa.Text(), nullable=True))

    if not _has_table("workflow_runs"):
        op.create_table(
            "workflow_runs",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("run_id", sa.String(), nullable=True),
            sa.Column("workflow_id", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="running"),
            sa.Column("total_nodes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completed_nodes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_nodes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("waiting_nodes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
            sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
        )
        op.create_index(
            "ix_workflow_runs_scope_updated",
            "workflow_runs",
            ["tenant_id", "workspace_id", "updated_at"],
        )
        op.create_index("ix_workflow_runs_run_id", "workflow_runs", ["run_id"])
        op.create_index("ix_workflow_runs_workflow_id", "workflow_runs", ["workflow_id"])


def downgrade() -> None:
    if _has_table("workflow_runs"):
        op.drop_index("ix_workflow_runs_workflow_id", table_name="workflow_runs")
        op.drop_index("ix_workflow_runs_run_id", table_name="workflow_runs")
        op.drop_index("ix_workflow_runs_scope_updated", table_name="workflow_runs")
        op.drop_table("workflow_runs")

    if _has_table("runs"):
        if _has_column("runs", "last_error"):
            op.drop_column("runs", "last_error")
        if _has_column("runs", "current_task_id"):
            with op.batch_alter_table("runs") as batch:
                batch.drop_constraint("fk_runs_current_task_id_tasks", type_="foreignkey")
                batch.drop_index("ix_runs_current_task_id")
                batch.drop_column("current_task_id")
