"""Add workspace scope, idempotency metadata, and leases to the outbox.

Revision ID: 20260714120000_outbox_workspace_leases
Revises: 20260611120000_regression_evaluation_tables
Create Date: 2026-07-14 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260714120000_outbox_workspace_leases"
down_revision = "20260611120000_regression_evaluation_tables"
branch_labels = None
depends_on = None


def _columns(conn) -> set[str]:
    return {column["name"] for column in sa.inspect(conn).get_columns("event_outbox")}


def _indexes(conn) -> set[str]:
    return {index["name"] for index in sa.inspect(conn).get_indexes("event_outbox")}


def upgrade() -> None:
    conn = op.get_bind()
    if "event_outbox" not in set(sa.inspect(conn).get_table_names()):
        return

    columns = _columns(conn)
    if "workspace_id" not in columns:
        op.add_column("event_outbox", sa.Column("workspace_id", sa.String(), nullable=True))
    if "idempotency_key" not in columns:
        op.add_column(
            "event_outbox", sa.Column("idempotency_key", sa.String(), nullable=True)
        )
        op.execute(
            sa.text(
                "UPDATE event_outbox SET idempotency_key = event_id "
                "WHERE idempotency_key IS NULL"
            )
        )
        op.alter_column("event_outbox", "idempotency_key", nullable=False)
    if "locked_at" not in columns:
        op.add_column("event_outbox", sa.Column("locked_at", sa.DateTime(), nullable=True))
    if "lock_owner" not in columns:
        op.add_column("event_outbox", sa.Column("lock_owner", sa.String(), nullable=True))
    if "lock_expires_at" not in columns:
        op.add_column(
            "event_outbox", sa.Column("lock_expires_at", sa.DateTime(), nullable=True)
        )

    indexes = _indexes(conn)
    for name, columns_ in (
        ("ix_event_outbox_workspace_id", ["workspace_id"]),
        ("ix_event_outbox_idempotency_key", ["idempotency_key"]),
        ("ix_event_outbox_lock_owner", ["lock_owner"]),
        ("ix_event_outbox_lock_expires_at", ["lock_expires_at"]),
    ):
        if name not in indexes:
            op.create_index(name, "event_outbox", columns_)


def downgrade() -> None:
    conn = op.get_bind()
    if "event_outbox" not in set(sa.inspect(conn).get_table_names()):
        return

    indexes = _indexes(conn)
    for name in (
        "ix_event_outbox_lock_expires_at",
        "ix_event_outbox_lock_owner",
        "ix_event_outbox_idempotency_key",
        "ix_event_outbox_workspace_id",
    ):
        if name in indexes:
            op.drop_index(name, table_name="event_outbox")

    columns = _columns(conn)
    for name in (
        "lock_expires_at",
        "lock_owner",
        "locked_at",
        "idempotency_key",
        "workspace_id",
    ):
        if name in columns:
            op.drop_column("event_outbox", name)
