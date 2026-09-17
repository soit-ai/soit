"""Outbox index diet: drop duplicated indexes, add the pending partial index.

Revision ID: 20260917100000
Revises: 20260831110000
Create Date: 2026-09-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260917100000"
down_revision: str | Sequence[str] | None = "20260831110000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # `uq_event_outbox_event_id` already indexes event_id; the single-column
    # status index is a prefix of (status, available_at).
    # A database created before either index existed must still upgrade.
    op.execute(sa.text("DROP INDEX IF EXISTS ix_event_outbox_event_id"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_event_outbox_status"))
    # The dispatcher only ever looks for pending rows that are due.
    op.create_index(
        "ix_event_outbox_pending_available_at",
        "event_outbox",
        ["available_at"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("ix_event_outbox_pending_available_at", table_name="event_outbox")
    op.create_index(op.f("ix_event_outbox_status"), "event_outbox", ["status"], unique=False)
    op.create_index(
        op.f("ix_event_outbox_event_id"), "event_outbox", ["event_id"], unique=False
    )
