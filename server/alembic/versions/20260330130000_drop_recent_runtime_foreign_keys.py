"""Drop recently introduced runtime foreign keys and keep relations in business code.

Revision ID: 20260330130000_drop_recent_runtime_foreign_keys
Revises: 20260330120000_scrub_task_output_duplicate_ids
Create Date: 2026-03-30 13:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260330130000_drop_recent_runtime_foreign_keys"
down_revision = "20260330120000_scrub_task_output_duplicate_ids"
branch_labels = None
depends_on = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in set(_inspector().get_table_names())


def _fk_names(table_name: str) -> set[str]:
    if not _has_table(table_name):
        return set()
    return {fk["name"] for fk in _inspector().get_foreign_keys(table_name) if fk.get("name")}


def _drop_fk_if_exists(table_name: str, constraint_name: str) -> None:
    if _has_table(table_name) and constraint_name in _fk_names(table_name):
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")


def upgrade() -> None:
    _drop_fk_if_exists("agent_bindings", "agent_bindings_agent_version_id_fkey")
    _drop_fk_if_exists("workflow_runs", "workflow_runs_run_id_fkey")
    _drop_fk_if_exists("workflow_runs", "workflow_runs_workflow_id_fkey")
    _drop_fk_if_exists("knowledge_chunks", "knowledge_chunks_knowledge_id_fkey")
    _drop_fk_if_exists("knowledge_ingest_tasks", "knowledge_ingest_tasks_document_id_fkey")
    _drop_fk_if_exists("run_artifacts", "run_artifacts_step_id_fkey")
    _drop_fk_if_exists("run_cost_entries", "run_cost_entries_step_id_fkey")


def downgrade() -> None:
    return None
