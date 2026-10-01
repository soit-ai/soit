"""Knowledge connectors: sources, per-item sync state and sync runs.

A knowledge source ties an external system (an S3-compatible bucket, a website)
to a knowledge base. ``knowledge_source_items`` remembers what each sync saw of
every remote item so the next one can tell new, changed, unchanged and removed
apart, and ``knowledge_sync_runs`` records each execution. A partial unique
index allows only one queued or running run per source. All three are new
tables; nothing existing changes.

Revision ID: 20261001110000
Revises: 20261001100000
Create Date: 2026-10-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261001110000"
down_revision: str | Sequence[str] | None = "20261001100000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCES = "knowledge_sources"
ITEMS = "knowledge_source_items"
RUNS = "knowledge_sync_runs"

ACTIVE_RUN = "status IN ('queued', 'running')"


def _scope_columns() -> list[sa.Column]:
    return [
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        SOURCES,
        sa.Column("id", sa.String(), primary_key=True),
        *_scope_columns(),
        sa.Column("knowledge_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("connector_kind", sa.String(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=True),
        sa.Column("secret_id", sa.String(), nullable=True),
        sa.Column("limits_json", sa.JSON(), nullable=True),
        sa.Column("schedule_cron", sa.String(), nullable=True),
        sa.Column("schedule_timezone", sa.String(), nullable=False, server_default="UTC"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("delete_removed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.String(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_counts_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("updated_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(f"ix_{SOURCES}_tenant_id", SOURCES, ["tenant_id"])
    op.create_index(f"ix_{SOURCES}_workspace_id", SOURCES, ["workspace_id"])
    op.create_index(f"ix_{SOURCES}_knowledge_id", SOURCES, ["knowledge_id"])
    op.create_index(f"ix_{SOURCES}_next_sync_at", SOURCES, ["next_sync_at"])

    op.create_table(
        ITEMS,
        sa.Column("id", sa.String(), primary_key=True),
        *_scope_columns(),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("doc_key", sa.String(), nullable=True),
        sa.Column("document_id", sa.String(), nullable=True),
        sa.Column("remote_etag", sa.String(), nullable=True),
        sa.Column("remote_modified", sa.String(), nullable=True),
        sa.Column("remote_size", sa.BigInteger(), nullable=True),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="present"),
        sa.Column("meta_json", sa.JSON(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(f"ix_{ITEMS}_tenant_id", ITEMS, ["tenant_id"])
    op.create_index(f"ix_{ITEMS}_workspace_id", ITEMS, ["workspace_id"])
    op.create_index(f"ix_{ITEMS}_source_id", ITEMS, ["source_id"])
    op.create_index(
        "uq_knowledge_source_items_source_external",
        ITEMS,
        ["source_id", "external_id"],
        unique=True,
    )

    op.create_table(
        RUNS,
        sa.Column("id", sa.String(), primary_key=True),
        *_scope_columns(),
        sa.Column("knowledge_id", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("trigger", sa.String(), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("added_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("removed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("outcomes_json", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("lease_owner", sa.String(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requested_by", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(f"ix_{RUNS}_tenant_id", RUNS, ["tenant_id"])
    op.create_index(f"ix_{RUNS}_workspace_id", RUNS, ["workspace_id"])
    op.create_index(f"ix_{RUNS}_knowledge_id", RUNS, ["knowledge_id"])
    op.create_index(f"ix_{RUNS}_source_id", RUNS, ["source_id"])
    op.create_index(f"ix_{RUNS}_status", RUNS, ["status"])
    op.create_index(f"ix_{RUNS}_lease_owner", RUNS, ["lease_owner"])
    op.create_index(f"ix_{RUNS}_lease_expires_at", RUNS, ["lease_expires_at"])
    op.create_index(
        "uq_knowledge_sync_runs_active_source",
        RUNS,
        ["source_id"],
        unique=True,
        postgresql_where=sa.text(ACTIVE_RUN),
        sqlite_where=sa.text(ACTIVE_RUN),
    )


def downgrade() -> None:
    op.drop_index("uq_knowledge_sync_runs_active_source", table_name=RUNS)
    for column in ("lease_expires_at", "lease_owner", "status", "source_id", "knowledge_id", "workspace_id", "tenant_id"):
        op.drop_index(f"ix_{RUNS}_{column}", table_name=RUNS)
    op.drop_table(RUNS)

    op.drop_index("uq_knowledge_source_items_source_external", table_name=ITEMS)
    for column in ("source_id", "workspace_id", "tenant_id"):
        op.drop_index(f"ix_{ITEMS}_{column}", table_name=ITEMS)
    op.drop_table(ITEMS)

    for column in ("next_sync_at", "knowledge_id", "workspace_id", "tenant_id"):
        op.drop_index(f"ix_{SOURCES}_{column}", table_name=SOURCES)
    op.drop_table(SOURCES)
