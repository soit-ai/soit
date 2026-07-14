"""Add observe_projection_records for Wave C consumer idempotency.

Revision ID: 20260324120000_observe_projection_records
Revises: 20260323120000_runs_workflow_runs_b5
Create Date: 2026-03-24 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260324120000_observe_projection_records"
down_revision = "20260323120000_runs_workflow_runs_b5"
branch_labels = None
depends_on = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in set(_inspector().get_table_names())


def upgrade() -> None:
    if not _has_table("observe_projection_records"):
        op.create_table(
            "observe_projection_records",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("consumer_name", sa.String(), nullable=False),
            sa.Column("event_id", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "consumer_name",
                "event_id",
                name="uq_observe_projection_consumer_event",
            ),
        )
        op.create_index(
            "ix_observe_projection_records_consumer_name",
            "observe_projection_records",
            ["consumer_name"],
        )
        op.create_index(
            "ix_observe_projection_records_event_id",
            "observe_projection_records",
            ["event_id"],
        )


def downgrade() -> None:
    if _has_table("observe_projection_records"):
        op.drop_index(
            "ix_observe_projection_records_event_id",
            table_name="observe_projection_records",
        )
        op.drop_index(
            "ix_observe_projection_records_consumer_name",
            table_name="observe_projection_records",
        )
        op.drop_table("observe_projection_records")
