"""plugin unified lifecycle tables

Revision ID: 20260602130000
Revises: 20260531120000
Create Date: 2026-06-02 13:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260602130000"
down_revision = "20260531120000_status_field_convergence"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    bind = op.get_bind()
    return set(sa.inspect(bind).get_table_names())


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    return {column["name"] for column in sa.inspect(bind).get_columns(table)}


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    if table in _tables() and column.name not in _columns(table):
        op.add_column(table, column)


def _create_index_if_missing(table: str, name: str, columns: list[str]) -> None:
    bind = op.get_bind()
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes(table)}
    if name not in indexes:
        op.create_index(name, table, columns)


def upgrade() -> None:
    tables = _tables()

    if "plugins" in tables:
        _add_column_if_missing("plugins", sa.Column("publisher", sa.String(), nullable=False, server_default="soit"))
        _add_column_if_missing("plugins", sa.Column("plugin_type", sa.String(), nullable=False, server_default="tool"))
        _add_column_if_missing("plugins", sa.Column("status", sa.String(), nullable=False, server_default="active"))
        _add_column_if_missing("plugins", sa.Column("current_version_id", sa.String(), nullable=True))
        _add_column_if_missing("plugins", sa.Column("published_version_id", sa.String(), nullable=True))
        _create_index_if_missing("plugins", "ix_plugins_publisher", ["publisher"])
        _create_index_if_missing("plugins", "ix_plugins_plugin_type", ["plugin_type"])
        _create_index_if_missing("plugins", "ix_plugins_status", ["status"])
        _create_index_if_missing("plugins", "ix_plugins_current_version_id", ["current_version_id"])
        _create_index_if_missing("plugins", "ix_plugins_published_version_id", ["published_version_id"])

    if "plugin_versions" not in tables:
        op.create_table(
            "plugin_versions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("plugin_id", sa.String(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("package_version", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="draft"),
            sa.Column("spec_schema", sa.String(), nullable=False, server_default="plugin.v1"),
            sa.Column("spec_json", sa.JSON(), nullable=False),
            sa.Column("manifest_json", sa.JSON(), nullable=False),
            sa.Column("package_sha256", sa.String(), nullable=True),
            sa.Column("artifact_summary_json", sa.JSON(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_plugin_versions_tenant_id", "plugin_versions", ["tenant_id"])
        op.create_index("ix_plugin_versions_workspace_id", "plugin_versions", ["workspace_id"])
        op.create_index("ix_plugin_versions_plugin_id", "plugin_versions", ["plugin_id"])
        op.create_index("ix_plugin_versions_package_version", "plugin_versions", ["package_version"])
        op.create_index("ix_plugin_versions_status", "plugin_versions", ["status"])

    if "plugin_releases" not in tables:
        op.create_table(
            "plugin_releases",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("plugin_id", sa.String(), nullable=False),
            sa.Column("plugin_version_id", sa.String(), nullable=False),
            sa.Column("action", sa.String(), nullable=False, server_default="publish"),
            sa.Column("scope", sa.String(), nullable=False, server_default="workspace"),
            sa.Column("status", sa.String(), nullable=False, server_default="published"),
            sa.Column("from_version_id", sa.String(), nullable=True),
            sa.Column("to_version_id", sa.String(), nullable=True),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("rollback_of_publish_id", sa.String(), nullable=True),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_plugin_releases_tenant_id", "plugin_releases", ["tenant_id"])
        op.create_index("ix_plugin_releases_workspace_id", "plugin_releases", ["workspace_id"])
        op.create_index("ix_plugin_releases_plugin_id", "plugin_releases", ["plugin_id"])
        op.create_index("ix_plugin_releases_plugin_version_id", "plugin_releases", ["plugin_version_id"])
        op.create_index("ix_plugin_releases_action", "plugin_releases", ["action"])
        op.create_index("ix_plugin_releases_status", "plugin_releases", ["status"])

    if "plugin_installations" in tables:
        _add_column_if_missing("plugin_installations", sa.Column("plugin_version_id", sa.String(), nullable=True))
        _add_column_if_missing("plugin_installations", sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
        _add_column_if_missing("plugin_installations", sa.Column("state", sa.String(), nullable=False, server_default="installed"))
        _add_column_if_missing("plugin_installations", sa.Column("updated_at", sa.DateTime(), nullable=True))
        _create_index_if_missing("plugin_installations", "ix_plugin_installations_plugin_version_id", ["plugin_version_id"])
        _create_index_if_missing("plugin_installations", "ix_plugin_installations_enabled", ["enabled"])
        _create_index_if_missing("plugin_installations", "ix_plugin_installations_state", ["state"])

    if "plugin_installed_artifacts" not in tables:
        op.create_table(
            "plugin_installed_artifacts",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("plugin_id", sa.String(), nullable=False),
            sa.Column("plugin_version_id", sa.String(), nullable=True),
            sa.Column("installation_id", sa.String(), nullable=True),
            sa.Column("artifact_kind", sa.String(), nullable=False),
            sa.Column("artifact_ref", sa.String(), nullable=False),
            sa.Column("artifact_id", sa.String(), nullable=True),
            sa.Column("artifact_version_id", sa.String(), nullable=True),
            sa.Column("state", sa.String(), nullable=False, server_default="enabled"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        for column in (
            "tenant_id",
            "workspace_id",
            "plugin_id",
            "plugin_version_id",
            "installation_id",
            "artifact_kind",
            "artifact_ref",
            "artifact_id",
            "artifact_version_id",
            "state",
            "enabled",
        ):
            op.create_index(f"ix_plugin_installed_artifacts_{column}", "plugin_installed_artifacts", [column])


def downgrade() -> None:
    tables = _tables()
    if "plugin_installed_artifacts" in tables:
        op.drop_table("plugin_installed_artifacts")
    if "plugin_releases" in tables:
        op.drop_table("plugin_releases")
    if "plugin_versions" in tables:
        op.drop_table("plugin_versions")
