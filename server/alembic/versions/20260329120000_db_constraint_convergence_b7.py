"""B7: converge database constraint names and core relationship columns.

Revision ID: 20260329120000_db_constraint_convergence_b7
Revises: 20260324120000_observe_projection_records
Create Date: 2026-03-29 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260329120000_db_constraint_convergence_b7"
down_revision = "20260324120000_observe_projection_records"
branch_labels = None
depends_on = None


INDEX_RENAMES: tuple[tuple[str, str], ...] = (
    ("ix_dataset_tenant_id", "ix_knowledge_tenant_id"),
    ("ix_dataset_workspace_id", "ix_knowledge_workspace_id"),
    ("ix_dataset_chunks_dataset_id", "ix_knowledge_chunks_knowledge_id"),
    ("ix_dataset_chunks_document_id", "ix_knowledge_chunks_document_id"),
    ("ix_dataset_chunks_tenant_id", "ix_knowledge_chunks_tenant_id"),
    ("ix_dataset_chunks_workspace_id", "ix_knowledge_chunks_workspace_id"),
    ("ix_dataset_documents_dataset_id", "ix_knowledge_documents_knowledge_id"),
    ("ix_dataset_documents_tenant_id", "ix_knowledge_documents_tenant_id"),
    ("ix_dataset_documents_workspace_id", "ix_knowledge_documents_workspace_id"),
    ("ix_dataset_indexs_dataset_id", "ix_knowledge_indexes_knowledge_id"),
    ("ix_dataset_indexs_tenant_id", "ix_knowledge_indexes_tenant_id"),
    ("ix_dataset_indexs_workspace_id", "ix_knowledge_indexes_workspace_id"),
    ("ix_dataset_ingest_tasks_dataset_id", "ix_knowledge_ingest_tasks_knowledge_id"),
    ("ix_dataset_ingest_tasks_document_id", "ix_knowledge_ingest_tasks_document_id"),
    ("ix_dataset_ingest_tasks_tenant_id", "ix_knowledge_ingest_tasks_tenant_id"),
    ("ix_dataset_ingest_tasks_workspace_id", "ix_knowledge_ingest_tasks_workspace_id"),
)

CONSTRAINT_RENAMES: tuple[tuple[str, str, str], ...] = (
    ("knowledge", "dataset_pkey", "knowledge_pkey"),
    ("knowledge_chunks", "dataset_chunks_pkey", "knowledge_chunks_pkey"),
    ("knowledge_chunks", "dataset_chunks_document_id_fkey", "knowledge_chunks_document_id_fkey"),
    ("knowledge_documents", "dataset_documents_pkey", "knowledge_documents_pkey"),
    ("knowledge_documents", "dataset_documents_dataset_id_fkey", "knowledge_documents_knowledge_id_fkey"),
    ("knowledge_indexes", "dataset_indexs_pkey", "knowledge_indexes_pkey"),
    ("knowledge_indexes", "dataset_indexs_dataset_id_fkey", "knowledge_indexes_knowledge_id_fkey"),
    ("knowledge_ingest_tasks", "dataset_ingest_tasks_pkey", "knowledge_ingest_tasks_pkey"),
    ("knowledge_ingest_tasks", "dataset_ingest_tasks_dataset_id_fkey", "knowledge_ingest_tasks_knowledge_id_fkey"),
)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_names() -> set[str]:
    return set(_inspector().get_table_names())


def _has_table(table_name: str) -> bool:
    return table_name in _table_names()


def _column_names(table_name: str) -> set[str]:
    if not _has_table(table_name):
        return set()
    return {column["name"] for column in _inspector().get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    if not _has_table(table_name):
        return set()
    return {index["name"] for index in _inspector().get_indexes(table_name)}


def _fk_names(table_name: str) -> set[str]:
    if not _has_table(table_name):
        return set()
    return {fk["name"] for fk in _inspector().get_foreign_keys(table_name) if fk.get("name")}


def _constraint_names(table_name: str) -> set[str]:
    names = _fk_names(table_name)
    if not _has_table(table_name):
        return names
    pk = _inspector().get_pk_constraint(table_name)
    if pk.get("name"):
        names.add(pk["name"])
    names.update(
        uq["name"]
        for uq in _inspector().get_unique_constraints(table_name)
        if uq.get("name")
    )
    return names


def _rename_index_if_needed(old_name: str, new_name: str) -> None:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND indexname = :index_name
            """
        ),
        {"index_name": old_name},
    )
    old_exists = int(result.scalar() or 0) > 0
    result = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND indexname = :index_name
            """
        ),
        {"index_name": new_name},
    )
    new_exists = int(result.scalar() or 0) > 0
    if old_exists and not new_exists:
        op.execute(sa.text(f'ALTER INDEX "{old_name}" RENAME TO "{new_name}"'))


def _rename_constraint_if_needed(table_name: str, old_name: str, new_name: str) -> None:
    names = _constraint_names(table_name)
    if old_name in names and new_name not in names:
        op.execute(sa.text(f'ALTER TABLE "{table_name}" RENAME CONSTRAINT "{old_name}" TO "{new_name}"'))


def _scalar_count(sql: str) -> int:
    result = op.get_bind().execute(sa.text(sql))
    return int(result.scalar() or 0)


def _ensure_no_rows(sql: str, error_message: str) -> None:
    if _scalar_count(sql) > 0:
        raise RuntimeError(error_message)


def _converge_knowledge_names() -> None:
    for old_name, new_name in INDEX_RENAMES:
        _rename_index_if_needed(old_name, new_name)

    for table_name, old_name, new_name in CONSTRAINT_RENAMES:
        if _has_table(table_name):
            _rename_constraint_if_needed(table_name, old_name, new_name)


def _backfill_knowledge_relationships() -> None:
    if _has_table("knowledge_chunks") and _has_table("knowledge_documents"):
        op.execute(
            sa.text(
                """
                UPDATE knowledge_chunks AS kc
                SET knowledge_id = kd.knowledge_id
                FROM knowledge_documents AS kd
                WHERE kc.document_id = kd.id
                  AND kc.knowledge_id IS DISTINCT FROM kd.knowledge_id
                """
            )
        )

    if _has_table("knowledge_ingest_tasks") and _has_table("knowledge_documents"):
        op.execute(
            sa.text(
                """
                UPDATE knowledge_ingest_tasks AS kit
                SET document_id = NULL
                WHERE kit.document_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1
                    FROM knowledge_documents AS kd
                    WHERE kd.id = kit.document_id
                  )
                """
            )
        )


def _backfill_workflow_runs() -> None:
    if _has_table("workflow_runs") and _has_table("runs"):
        op.execute(
            sa.text(
                """
                UPDATE workflow_runs AS wr
                SET workflow_id = r.subject_id
                FROM runs AS r
                WHERE wr.run_id = r.id
                  AND wr.workflow_id IS NULL
                  AND r.subject_kind = 'workflow'
                  AND r.subject_id IS NOT NULL
                """
            )
        )


def _clear_orphan_step_refs() -> None:
    if _has_table("run_artifacts") and _has_table("run_steps"):
        op.execute(
            sa.text(
                """
                UPDATE run_artifacts AS ra
                SET step_id = NULL
                WHERE ra.step_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1
                    FROM run_steps AS rs
                    WHERE rs.id = ra.step_id
                  )
                """
            )
        )

    if _has_table("run_cost_entries") and _has_table("run_steps"):
        op.execute(
            sa.text(
                """
                UPDATE run_cost_entries AS rce
                SET step_id = NULL
                WHERE rce.step_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1
                    FROM run_steps AS rs
                    WHERE rs.id = rce.step_id
                  )
                """
            )
        )


def _tighten_nullability() -> None:
    if _has_table("agent_bindings") and "agent_version_id" in _column_names("agent_bindings"):
        _ensure_no_rows(
            "SELECT COUNT(*) FROM agent_bindings WHERE agent_version_id IS NULL",
            "Cannot set agent_bindings.agent_version_id NOT NULL while NULL rows still exist.",
        )
        with op.batch_alter_table("agent_bindings") as batch_op:
            batch_op.alter_column("agent_version_id", existing_type=sa.String(), nullable=False)

    if _has_table("workflow_runs"):
        _ensure_no_rows(
            "SELECT COUNT(*) FROM workflow_runs WHERE run_id IS NULL",
            "Cannot set workflow_runs.run_id NOT NULL while NULL rows still exist.",
        )
        _ensure_no_rows(
            "SELECT COUNT(*) FROM workflow_runs WHERE workflow_id IS NULL",
            "Cannot set workflow_runs.workflow_id NOT NULL while NULL rows still exist.",
        )
        _ensure_no_rows(
            """
            SELECT COUNT(*)
            FROM workflow_runs AS wr
            LEFT JOIN workflows AS wf ON wf.id = wr.workflow_id
            WHERE wr.workflow_id IS NOT NULL
              AND wf.id IS NULL
            """,
            "Cannot enforce workflow_runs.workflow_id foreign key because orphan workflow references still exist.",
        )
        with op.batch_alter_table("workflow_runs") as batch_op:
            batch_op.alter_column("run_id", existing_type=sa.String(), nullable=False)
            batch_op.alter_column("workflow_id", existing_type=sa.String(), nullable=False)


def upgrade() -> None:
    _converge_knowledge_names()
    _backfill_knowledge_relationships()
    _backfill_workflow_runs()
    _clear_orphan_step_refs()
    _tighten_nullability()


def downgrade() -> None:
    if _has_table("workflow_runs"):
        with op.batch_alter_table("workflow_runs") as batch_op:
            batch_op.alter_column("workflow_id", existing_type=sa.String(), nullable=True)
            batch_op.alter_column("run_id", existing_type=sa.String(), nullable=True)

    if _has_table("agent_bindings"):
        with op.batch_alter_table("agent_bindings") as batch_op:
            batch_op.alter_column("agent_version_id", existing_type=sa.String(), nullable=True)

    for table_name, old_name, new_name in reversed(CONSTRAINT_RENAMES):
        if _has_table(table_name):
            _rename_constraint_if_needed(table_name, new_name, old_name)

    for old_name, new_name in reversed(INDEX_RENAMES):
        _rename_index_if_needed(new_name, old_name)
