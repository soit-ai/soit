"""Squash runtime and knowledge refactor migrations into a single revision.

Revision ID: 20260309120000_squash_runtime_knowledge_refactor
Revises: 20260307162000_drop_response_tool_calls
Create Date: 2026-03-09 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260309120000_squash_runtime_knowledge_refactor"
down_revision = "20260307162000_drop_response_tool_calls"
branch_labels = None
depends_on = None


LEGACY_TABLES = (
    "app_component_edges",
    "app_components",
    "app_installations",
    "app_market",
    "app_version_refs",
    "app_versions",
    "apps",
    "messages",
    "conversations",
)

THREAD_COLUMNS: tuple[sa.Column, ...] = (
    sa.Column("thread_type", sa.String(), nullable=True),
    sa.Column("source", sa.String(), nullable=True),
    sa.Column("owner_user_id", sa.String(), nullable=True),
    sa.Column("summary", sa.Text(), nullable=True),
    sa.Column("system_prompt", sa.Text(), nullable=True),
    sa.Column("default_model_ref", sa.String(), nullable=True),
    sa.Column("default_temperature", sa.Float(), nullable=True),
    sa.Column("default_max_tokens", sa.Integer(), nullable=True),
    sa.Column("default_top_p", sa.Float(), nullable=True),
    sa.Column("context_window", sa.Integer(), nullable=True),
    sa.Column("max_history_messages", sa.Integer(), nullable=True),
    sa.Column("max_history_chars", sa.Integer(), nullable=True),
    sa.Column("message_count", sa.Integer(), nullable=True),
    sa.Column("last_message_at", sa.DateTime(), nullable=True),
    sa.Column("last_user_message_at", sa.DateTime(), nullable=True),
    sa.Column("last_assistant_message_at", sa.DateTime(), nullable=True),
    sa.Column("archived_at", sa.DateTime(), nullable=True),
    sa.Column("pinned_at", sa.DateTime(), nullable=True),
    sa.Column("knowledge_config_json", sa.JSON(), nullable=True),
    sa.Column("tool_config_json", sa.JSON(), nullable=True),
)

THREAD_MESSAGE_COLUMNS: tuple[sa.Column, ...] = (
    sa.Column("task_id", sa.String(), nullable=True),
    sa.Column("response_id", sa.String(), nullable=True),
    sa.Column("sequence_no", sa.Integer(), nullable=True),
    sa.Column("status", sa.String(), nullable=True),
    sa.Column("content_json", sa.JSON(), nullable=True),
    sa.Column("summary", sa.Text(), nullable=True),
    sa.Column("model_ref", sa.String(), nullable=True),
    sa.Column("tokens_prompt", sa.Integer(), nullable=True),
    sa.Column("tokens_completion", sa.Integer(), nullable=True),
    sa.Column("finish_reason", sa.String(), nullable=True),
    sa.Column("citations_json", sa.JSON(), nullable=True),
    sa.Column("attachments_json", sa.JSON(), nullable=True),
    sa.Column("tool_calls_json", sa.JSON(), nullable=True),
    sa.Column("error_code", sa.String(), nullable=True),
    sa.Column("error_message", sa.Text(), nullable=True),
    sa.Column("edited_at", sa.DateTime(), nullable=True),
    sa.Column("deleted_at", sa.DateTime(), nullable=True),
)

TABLE_RENAMES = [
    ("dataset", "knowledge"),
    ("dataset_documents", "knowledge_documents"),
    ("dataset_chunks", "knowledge_chunks"),
    ("dataset_indexs", "knowledge_indexes"),
    ("dataset_ingest_tasks", "knowledge_ingest_tasks"),
]

COLUMN_RENAMES = [
    ("knowledge_documents", "dataset_id", "knowledge_id"),
    ("knowledge_chunks", "dataset_id", "knowledge_id"),
    ("knowledge_indexes", "dataset_id", "knowledge_id"),
    ("knowledge_ingest_tasks", "dataset_id", "knowledge_id"),
]


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


def _uq_names(table_name: str) -> set[str]:
    if not _has_table(table_name):
        return set()
    return {uq["name"] for uq in _inspector().get_unique_constraints(table_name) if uq.get("name")}


def _add_missing_columns(table_name: str, columns: tuple[sa.Column, ...]) -> None:
    existing = _column_names(table_name)
    if not existing:
        return
    with op.batch_alter_table(table_name) as batch_op:
        for column in columns:
            if column.name not in existing:
                batch_op.add_column(column)


def _rename_table_if_needed(old_name: str, new_name: str) -> None:
    if _has_table(old_name) and not _has_table(new_name):
        op.rename_table(old_name, new_name)


def _rename_column_if_needed(table_name: str, old_name: str, new_name: str) -> None:
    existing = _column_names(table_name)
    if old_name in existing and new_name not in existing:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(old_name, new_column_name=new_name)


def _rewrite_run_input_summary(old_key: str, new_key: str) -> None:
    if not _has_table("runs") or "input_summary" not in _column_names("runs"):
        return
    op.execute(
        sa.text(
            "UPDATE runs "
            "SET input_summary = REPLACE(input_summary, :old_key, :new_key) "
            "WHERE input_summary IS NOT NULL AND input_summary LIKE :pattern"
        ).bindparams(old_key=old_key, new_key=new_key, pattern=f"%{old_key}%")
    )


def _upgrade_threads() -> None:
    if not _has_table("threads") or not _has_table("thread_messages"):
        return

    _add_missing_columns("threads", THREAD_COLUMNS)
    _add_missing_columns("thread_messages", THREAD_MESSAGE_COLUMNS)

    op.execute(
        sa.text(
            """
            UPDATE threads
            SET
              thread_type = COALESCE(thread_type, 'chat'),
              source = COALESCE(source, metadata_json->>'source', 'runtime.thread'),
              owner_user_id = COALESCE(owner_user_id, created_by, updated_by),
              summary = COALESCE(summary, NULLIF(left(regexp_replace(COALESCE(title, ''), '\\s+', ' ', 'g'), 280), '')),
              system_prompt = COALESCE(system_prompt, metadata_json->>'system_prompt'),
              default_model_ref = COALESCE(default_model_ref, metadata_json->>'default_model_ref'),
              default_temperature = COALESCE(default_temperature, NULLIF(metadata_json->>'default_temperature', '')::double precision),
              default_max_tokens = COALESCE(default_max_tokens, NULLIF(metadata_json->>'default_max_tokens', '')::integer),
              default_top_p = COALESCE(default_top_p, NULLIF(metadata_json->>'default_top_p', '')::double precision),
              context_window = COALESCE(context_window, NULLIF(metadata_json->>'context_window', '')::integer),
              max_history_messages = COALESCE(max_history_messages, NULLIF(metadata_json->>'max_history_messages', '')::integer),
              max_history_chars = COALESCE(max_history_chars, NULLIF(metadata_json->>'max_history_chars', '')::integer),
              knowledge_config_json = COALESCE(knowledge_config_json, '{}'::json),
              tool_config_json = COALESCE(tool_config_json, '{}'::json),
              archived_at = CASE
                WHEN status = 'archived' THEN COALESCE(archived_at, updated_at, created_at)
                ELSE archived_at
              END
            """
        )
    )

    op.execute(
        sa.text(
            """
            WITH thread_stats AS (
              SELECT
                thread_id,
                COUNT(*) FILTER (WHERE deleted_at IS NULL) AS message_count,
                MAX(created_at) FILTER (WHERE deleted_at IS NULL) AS last_message_at,
                MAX(created_at) FILTER (WHERE role = 'user' AND deleted_at IS NULL) AS last_user_message_at,
                MAX(created_at) FILTER (WHERE role = 'assistant' AND deleted_at IS NULL) AS last_assistant_message_at,
                MIN(content) FILTER (WHERE role = 'user' AND deleted_at IS NULL) AS first_user_content
              FROM thread_messages
              GROUP BY thread_id
            )
            UPDATE threads t
            SET
              message_count = COALESCE(s.message_count, 0),
              last_message_at = s.last_message_at,
              last_user_message_at = s.last_user_message_at,
              last_assistant_message_at = s.last_assistant_message_at,
              summary = COALESCE(
                t.summary,
                NULLIF(left(regexp_replace(COALESCE(s.first_user_content, ''), '\\s+', ' ', 'g'), 280), '')
              )
            FROM thread_stats s
            WHERE t.id = s.thread_id
            """
        )
    )

    op.execute(sa.text("UPDATE threads SET message_count = COALESCE(message_count, 0)"))
    op.execute(sa.text("UPDATE threads SET knowledge_config_json = COALESCE(knowledge_config_json, '{}'::json)"))
    op.execute(sa.text("UPDATE threads SET tool_config_json = COALESCE(tool_config_json, '{}'::json)"))

    op.execute(
        sa.text(
            """
            WITH ranked AS (
              SELECT
                id,
                ROW_NUMBER() OVER (PARTITION BY thread_id ORDER BY created_at ASC, id ASC) AS seq
              FROM thread_messages
            )
            UPDATE thread_messages tm
            SET
              sequence_no = ranked.seq,
              status = COALESCE(tm.status, 'completed'),
              content_json = COALESCE(
                tm.content_json,
                json_build_object(
                  'type', COALESCE(tm.message_type, 'text'),
                  'text', tm.content,
                  'parts', json_build_array(json_build_object('type', 'text', 'text', tm.content))
                )
              ),
              summary = COALESCE(tm.summary, NULLIF(left(regexp_replace(COALESCE(tm.content, ''), '\\s+', ' ', 'g'), 280), '')),
              response_id = COALESCE(tm.response_id, NULLIF(tm.metadata_json->>'response_id', '')),
              task_id = COALESCE(tm.task_id, NULLIF(tm.metadata_json->>'task_id', '')),
              model_ref = COALESCE(tm.model_ref, NULLIF(tm.metadata_json->>'model_ref', ''), NULLIF(tm.metadata_json->>'model', '')),
              tokens_prompt = COALESCE(
                tm.tokens_prompt,
                CASE
                  WHEN (tm.metadata_json->>'tokens_prompt') ~ '^[0-9]+$' THEN (tm.metadata_json->>'tokens_prompt')::integer
                  ELSE NULL
                END
              ),
              tokens_completion = COALESCE(
                tm.tokens_completion,
                CASE
                  WHEN (tm.metadata_json->>'tokens_completion') ~ '^[0-9]+$' THEN (tm.metadata_json->>'tokens_completion')::integer
                  ELSE NULL
                END
              ),
              finish_reason = COALESCE(tm.finish_reason, NULLIF(tm.metadata_json->>'finish_reason', '')),
              citations_json = COALESCE(
                tm.citations_json,
                CASE WHEN json_typeof(tm.metadata_json->'citations') = 'array' THEN tm.metadata_json->'citations' ELSE '[]'::json END
              ),
              attachments_json = COALESCE(
                tm.attachments_json,
                CASE WHEN json_typeof(tm.metadata_json->'attachments') = 'array' THEN tm.metadata_json->'attachments' ELSE '[]'::json END
              ),
              tool_calls_json = COALESCE(
                tm.tool_calls_json,
                CASE WHEN json_typeof(tm.metadata_json->'tool_calls') = 'array' THEN tm.metadata_json->'tool_calls' ELSE '[]'::json END
              ),
              error_code = COALESCE(tm.error_code, NULLIF(tm.metadata_json->>'error_code', '')),
              error_message = COALESCE(tm.error_message, NULLIF(tm.metadata_json->>'error_message', ''))
            FROM ranked
            WHERE tm.id = ranked.id
            """
        )
    )

    op.execute(sa.text("UPDATE thread_messages SET status = COALESCE(status, 'completed')"))
    op.execute(sa.text("UPDATE thread_messages SET citations_json = COALESCE(citations_json, '[]'::json)"))
    op.execute(sa.text("UPDATE thread_messages SET attachments_json = COALESCE(attachments_json, '[]'::json)"))
    op.execute(sa.text("UPDATE thread_messages SET tool_calls_json = COALESCE(tool_calls_json, '[]'::json)"))
    op.execute(
        sa.text(
            """
            UPDATE thread_messages tm
            SET response_id = NULL
            WHERE response_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM responses r WHERE r.id = tm.response_id)
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE thread_messages tm
            SET task_id = NULL
            WHERE task_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM tasks t WHERE t.id = tm.task_id)
            """
        )
    )

    with op.batch_alter_table("threads") as batch_op:
        batch_op.alter_column("thread_type", existing_type=sa.String(), nullable=False)
        batch_op.alter_column("message_count", existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table("thread_messages") as batch_op:
        batch_op.alter_column("sequence_no", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("status", existing_type=sa.String(), nullable=False)

    thread_indexes = _index_names("threads")
    if "ix_threads_scope_updated" not in thread_indexes:
        op.create_index("ix_threads_scope_updated", "threads", ["tenant_id", "workspace_id", "updated_at"])
    if "ix_threads_status_archived" not in thread_indexes:
        op.create_index("ix_threads_status_archived", "threads", ["status", "archived_at"])
    if "ix_threads_owner_updated" not in thread_indexes:
        op.create_index("ix_threads_owner_updated", "threads", ["owner_user_id", "updated_at"])

    message_indexes = _index_names("thread_messages")
    if "ix_thread_messages_thread_sequence" not in message_indexes:
        op.create_index("ix_thread_messages_thread_sequence", "thread_messages", ["thread_id", "sequence_no"])
    if "ix_thread_messages_status_created" not in message_indexes:
        op.create_index("ix_thread_messages_status_created", "thread_messages", ["status", "created_at"])

    if "uq_thread_messages_thread_sequence" not in _uq_names("thread_messages"):
        with op.batch_alter_table("thread_messages") as batch_op:
            batch_op.create_unique_constraint("uq_thread_messages_thread_sequence", ["thread_id", "sequence_no"])

    fk_names = _fk_names("thread_messages")
    if "fk_thread_messages_task_id_tasks" not in fk_names:
        op.create_foreign_key("fk_thread_messages_task_id_tasks", "thread_messages", "tasks", ["task_id"], ["id"])
    if "fk_thread_messages_response_id_responses" not in fk_names:
        op.create_foreign_key(
            "fk_thread_messages_response_id_responses",
            "thread_messages",
            "responses",
            ["response_id"],
            ["id"],
        )


def _upgrade_agents_and_workflows() -> None:
    if _has_table("agents"):
        columns = _column_names("agents")
        if "icon_url" not in columns:
            op.add_column("agents", sa.Column("icon_url", sa.String(length=2000), nullable=True))
        if "category" not in columns:
            op.add_column("agents", sa.Column("category", sa.String(length=128), nullable=True))
        if "is_public" not in columns:
            op.add_column("agents", sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()))
        if "featured" not in columns:
            op.add_column("agents", sa.Column("featured", sa.Boolean(), nullable=False, server_default=sa.false()))
        if "downloads_count" not in columns:
            op.add_column("agents", sa.Column("downloads_count", sa.Integer(), nullable=False, server_default="0"))
        if "rating" not in columns:
            op.add_column("agents", sa.Column("rating", sa.Float(), nullable=True))
        if "reviews_count" not in columns:
            op.add_column("agents", sa.Column("reviews_count", sa.Integer(), nullable=False, server_default="0"))
        if "published_at" not in columns:
            op.add_column("agents", sa.Column("published_at", sa.DateTime(), nullable=True))

        indexes = _index_names("agents")
        if "ix_agents_tenant_workspace_category" not in indexes:
            op.create_index("ix_agents_tenant_workspace_category", "agents", ["tenant_id", "workspace_id", "category"])
        if "ix_agents_tenant_workspace_featured" not in indexes:
            op.create_index("ix_agents_tenant_workspace_featured", "agents", ["tenant_id", "workspace_id", "featured"])

        op.alter_column("agents", "is_public", server_default=None)
        op.alter_column("agents", "featured", server_default=None)
        op.alter_column("agents", "downloads_count", server_default=None)
        op.alter_column("agents", "reviews_count", server_default=None)

    if _has_table("workflows"):
        columns = _column_names("workflows")
        if "summary" not in columns:
            op.add_column("workflows", sa.Column("summary", sa.Text(), nullable=True))
        if "icon_url" not in columns:
            op.add_column("workflows", sa.Column("icon_url", sa.String(length=2000), nullable=True))
        if "category" not in columns:
            op.add_column("workflows", sa.Column("category", sa.String(length=128), nullable=True))
        if "tags" not in columns:
            op.add_column("workflows", sa.Column("tags", sa.JSON(), nullable=True))
        if "owner_user_id" not in columns:
            op.add_column("workflows", sa.Column("owner_user_id", sa.String(length=255), nullable=True))

        indexes = _index_names("workflows")
        if "ix_workflows_tenant_workspace_category" not in indexes:
            op.create_index(
                "ix_workflows_tenant_workspace_category",
                "workflows",
                ["tenant_id", "workspace_id", "category"],
            )
        if "ix_workflows_tenant_workspace_owner" not in indexes:
            op.create_index(
                "ix_workflows_tenant_workspace_owner",
                "workflows",
                ["tenant_id", "workspace_id", "owner_user_id"],
            )


def _upgrade_runs() -> None:
    if not _has_table("runs"):
        return
    indexes = _index_names("runs")
    for index_name in ("ix_runs_scope_app_started", "ix_runs_app_id", "ix_runs_app_type"):
        if index_name in indexes:
            op.drop_index(index_name, table_name="runs")

    columns = _column_names("runs")
    with op.batch_alter_table("runs") as batch_op:
        if "app_id" in columns:
            batch_op.drop_column("app_id")
        if "app_type" in columns:
            batch_op.drop_column("app_type")


def _upgrade_knowledge_storage_names() -> None:
    for old_name, new_name in TABLE_RENAMES:
        _rename_table_if_needed(old_name, new_name)

    for table_name, old_name, new_name in COLUMN_RENAMES:
        _rename_column_if_needed(table_name, old_name, new_name)

    _rewrite_run_input_summary("dataset_id=", "knowledge_id=")


def upgrade() -> None:
    existing_tables = _table_names()
    for table_name in LEGACY_TABLES:
        if table_name in existing_tables:
            op.execute(sa.text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))

    _upgrade_threads()
    _upgrade_agents_and_workflows()
    _upgrade_runs()
    _upgrade_knowledge_storage_names()


def downgrade() -> None:
    # Squashed refactor revision includes destructive cleanup and table renames.
    # Restoring the pre-refactor AppCenter/conversation schema is intentionally unsupported.
    return None
