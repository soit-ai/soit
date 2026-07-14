"""add provider slug and configuration json

Revision ID: 20260608100000_provider_configuration_json
Revises: 20260607100000_knowledge_index_last_run_id
Create Date: 2026-06-08 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260608100000_provider_configuration_json"
down_revision = "20260607100000_knowledge_index_last_run_id"
branch_labels = None
depends_on = None


def _columns(conn, table_name: str) -> set[str]:
    if table_name not in sa.inspect(conn).get_table_names():
        return set()
    return {column["name"] for column in sa.inspect(conn).get_columns(table_name)}


def _indexes(conn, table_name: str) -> set[str]:
    if table_name not in sa.inspect(conn).get_table_names():
        return set()
    return {index["name"] for index in sa.inspect(conn).get_indexes(table_name)}


def _backfill_provider_slugs(conn) -> None:
    providers = conn.execute(
        sa.text("SELECT id, tenant_id, workspace_id, kind, slug FROM providers ORDER BY created_at, id")
    ).mappings()
    used: set[tuple[str, str, str]] = set()

    for provider in providers:
        current_slug = (provider["slug"] or "").strip()
        base_slug = current_slug or provider["kind"] or "provider"
        slug = base_slug
        key = (provider["tenant_id"], provider["workspace_id"], slug)
        if key in used:
            suffix = str(provider["id"])[-8:]
            slug = f"{base_slug}-{suffix}"
            key = (provider["tenant_id"], provider["workspace_id"], slug)
        used.add(key)
        conn.execute(
            sa.text("UPDATE providers SET slug = :slug WHERE id = :provider_id"),
            {"slug": slug, "provider_id": provider["id"]},
        )


def upgrade() -> None:
    conn = op.get_bind()
    if "providers" not in sa.inspect(conn).get_table_names():
        return

    columns = _columns(conn, "providers")
    if "slug" not in columns:
        op.add_column("providers", sa.Column("slug", sa.String(), nullable=True))
    if "connection_config_json" not in columns:
        op.add_column("providers", sa.Column("connection_config_json", sa.JSON(), nullable=True))
    if "auth_config_json" not in columns:
        op.add_column("providers", sa.Column("auth_config_json", sa.JSON(), nullable=True))
    if "runtime_config_json" not in columns:
        op.add_column("providers", sa.Column("runtime_config_json", sa.JSON(), nullable=True))
    if "governance_config_json" not in columns:
        op.add_column("providers", sa.Column("governance_config_json", sa.JSON(), nullable=True))

    _backfill_provider_slugs(conn)

    if "slug" in _columns(conn, "providers"):
        with op.batch_alter_table("providers") as batch_op:
            batch_op.alter_column("slug", existing_type=sa.String(), nullable=False)

    if "uq_providers_workspace_slug" not in _indexes(conn, "providers"):
        op.create_index(
            "uq_providers_workspace_slug",
            "providers",
            ["tenant_id", "workspace_id", "slug"],
            unique=True,
        )


def downgrade() -> None:
    conn = op.get_bind()
    if "providers" not in sa.inspect(conn).get_table_names():
        return

    indexes = _indexes(conn, "providers")
    if "uq_providers_workspace_slug" in indexes:
        op.drop_index("uq_providers_workspace_slug", table_name="providers")

    columns = _columns(conn, "providers")
    for column_name in (
        "governance_config_json",
        "runtime_config_json",
        "auth_config_json",
        "connection_config_json",
        "slug",
    ):
        if column_name in columns:
            op.drop_column("providers", column_name)
