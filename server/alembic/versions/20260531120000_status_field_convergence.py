"""Converge legacy boolean status fields.

Revision ID: 20260531120000_status_field_convergence
Revises: 20260330170000_skill_workflow_release_fields
Create Date: 2026-05-31 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260531120000_status_field_convergence"
down_revision = "20260330170000_skill_workflow_release_fields"
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


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _has_table(table_name) or column.name in _column_names(table_name):
        return
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.add_column(column)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if not _has_table(table_name) or column_name not in _column_names(table_name):
        return
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_column(column_name)


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    if not _has_table(table_name) or index_name in _index_names(table_name):
        return
    op.create_index(index_name, table_name, columns)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if not _has_table(table_name) or index_name not in _index_names(table_name):
        return
    op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    if _has_table("plugins"):
        plugin_columns = _column_names("plugins")
        _add_column_if_missing(
            "plugins",
            sa.Column("publish_status", sa.String(), nullable=False, server_default="draft"),
        )
        if "published" in plugin_columns:
            op.execute(
                sa.text(
                    """
                    UPDATE plugins
                    SET publish_status = CASE WHEN published THEN 'published' ELSE 'draft' END
                    """
                )
            )
            _drop_index_if_exists("plugins", "ix_plugins_published")
            _drop_column_if_exists("plugins", "published")
        _create_index_if_missing("plugins", "ix_plugins_publish_status", ["publish_status"])

    if _has_table("platform_models"):
        platform_columns = _column_names("platform_models")
        _add_column_if_missing(
            "platform_models",
            sa.Column("status", sa.String(), nullable=False, server_default="active"),
        )
        _add_column_if_missing("platform_models", sa.Column("lifecycle_status", sa.String(), nullable=True))
        if "is_active" in platform_columns:
            op.execute(
                sa.text(
                    """
                    UPDATE platform_models
                    SET status = CASE WHEN is_active THEN 'active' ELSE 'disabled' END
                    """
                )
            )
            _drop_column_if_exists("platform_models", "is_active")
        if "lifecycle" in platform_columns:
            op.execute(sa.text("UPDATE platform_models SET lifecycle_status = lifecycle WHERE lifecycle_status IS NULL"))
            _drop_column_if_exists("platform_models", "lifecycle")
        _create_index_if_missing("platform_models", "ix_platform_models_status", ["status"])

    if _has_table("provider_models"):
        provider_model_columns = _column_names("provider_models")
        _add_column_if_missing(
            "provider_models",
            sa.Column("status", sa.String(), nullable=False, server_default="active"),
        )
        _add_column_if_missing("provider_models", sa.Column("lifecycle_status", sa.String(), nullable=True))
        if "enabled" in provider_model_columns:
            op.execute(
                sa.text(
                    """
                    UPDATE provider_models
                    SET status = CASE WHEN enabled THEN 'active' ELSE 'disabled' END
                    """
                )
            )
            _drop_column_if_exists("provider_models", "enabled")
        if "lifecycle" in provider_model_columns:
            op.execute(sa.text("UPDATE provider_models SET lifecycle_status = lifecycle WHERE lifecycle_status IS NULL"))
            _drop_column_if_exists("provider_models", "lifecycle")
        _create_index_if_missing("provider_models", "ix_provider_models_status", ["status"])


def downgrade() -> None:
    if _has_table("provider_models"):
        provider_model_columns = _column_names("provider_models")
        _add_column_if_missing("provider_models", sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
        _add_column_if_missing("provider_models", sa.Column("lifecycle", sa.String(), nullable=True))
        if "status" in provider_model_columns:
            op.execute(sa.text("UPDATE provider_models SET enabled = CASE WHEN status = 'active' THEN TRUE ELSE FALSE END"))
            _drop_index_if_exists("provider_models", "ix_provider_models_status")
            _drop_column_if_exists("provider_models", "status")
        if "lifecycle_status" in provider_model_columns:
            op.execute(sa.text("UPDATE provider_models SET lifecycle = lifecycle_status WHERE lifecycle IS NULL"))
            _drop_column_if_exists("provider_models", "lifecycle_status")

    if _has_table("platform_models"):
        platform_columns = _column_names("platform_models")
        _add_column_if_missing("platform_models", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
        _add_column_if_missing("platform_models", sa.Column("lifecycle", sa.String(), nullable=True))
        if "status" in platform_columns:
            op.execute(sa.text("UPDATE platform_models SET is_active = CASE WHEN status = 'active' THEN TRUE ELSE FALSE END"))
            _drop_index_if_exists("platform_models", "ix_platform_models_status")
            _drop_column_if_exists("platform_models", "status")
        if "lifecycle_status" in platform_columns:
            op.execute(sa.text("UPDATE platform_models SET lifecycle = lifecycle_status WHERE lifecycle IS NULL"))
            _drop_column_if_exists("platform_models", "lifecycle_status")

    if _has_table("plugins"):
        plugin_columns = _column_names("plugins")
        _add_column_if_missing("plugins", sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()))
        if "publish_status" in plugin_columns:
            op.execute(sa.text("UPDATE plugins SET published = CASE WHEN publish_status = 'published' THEN TRUE ELSE FALSE END"))
            _drop_index_if_exists("plugins", "ix_plugins_publish_status")
            _drop_column_if_exists("plugins", "publish_status")
        _create_index_if_missing("plugins", "ix_plugins_published", ["published"])
