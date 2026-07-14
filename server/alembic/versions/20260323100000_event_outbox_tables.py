"""Add event_outbox, event_consumer_checkpoint, dead_letter_events.

Revision ID: 20260323100000_event_outbox_tables
Revises: 20260309153000_drop_run_app_version_id
Create Date: 2026-03-23 10:00:00

Aligned with server/docs/architecture/OUTBOX_EVENT_MODEL.md.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260323100000_event_outbox_tables"
down_revision = "20260309153000_drop_run_app_version_id"
branch_labels = None
depends_on = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in set(_inspector().get_table_names())


def upgrade() -> None:
    if not _has_table("event_outbox"):
        op.create_table(
            "event_outbox",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("event_id", sa.String(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("event_version", sa.String(), nullable=False, server_default="1"),
            sa.Column("tenant_id", sa.String(), nullable=True),
            sa.Column("subject_type", sa.String(), nullable=True),
            sa.Column("subject_id", sa.String(), nullable=True),
            sa.Column("run_id", sa.String(), nullable=True),
            sa.Column("task_id", sa.String(), nullable=True),
            sa.Column("thread_id", sa.String(), nullable=True),
            sa.Column("workflow_run_id", sa.String(), nullable=True),
            sa.Column("correlation_id", sa.String(), nullable=True),
            sa.Column("causation_id", sa.String(), nullable=True),
            sa.Column("producer", sa.String(), nullable=True),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("headers_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("available_at", sa.DateTime(), nullable=False),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("occurred_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("event_id", name="uq_event_outbox_event_id"),
        )
        op.create_index(
            "ix_event_outbox_status_available_at",
            "event_outbox",
            ["status", "available_at"],
        )
        op.create_index("ix_event_outbox_correlation_id", "event_outbox", ["correlation_id"])
        op.create_index(
            "ix_event_outbox_subject_type_subject_id",
            "event_outbox",
            ["subject_type", "subject_id"],
        )
        op.create_index("ix_event_outbox_run_id", "event_outbox", ["run_id"])
        op.create_index(
            "ix_event_outbox_workflow_run_id",
            "event_outbox",
            ["workflow_run_id"],
        )

    if not _has_table("event_consumer_checkpoint"):
        op.create_table(
            "event_consumer_checkpoint",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("consumer_name", sa.String(), nullable=False),
            sa.Column("event_id", sa.String(), nullable=False),
            sa.Column("processed_at", sa.DateTime(), nullable=False),
            sa.Column("result", sa.String(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.UniqueConstraint(
                "consumer_name",
                "event_id",
                name="uq_event_consumer_checkpoint_consumer_event",
            ),
        )
        op.create_index(
            "ix_event_consumer_checkpoint_event_id",
            "event_consumer_checkpoint",
            ["event_id"],
        )

    if not _has_table("dead_letter_events"):
        op.create_table(
            "dead_letter_events",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("event_id", sa.String(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("consumer_name", sa.String(), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("failed_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_dead_letter_events_event_id",
            "dead_letter_events",
            ["event_id"],
        )


def downgrade() -> None:
    if _has_table("dead_letter_events"):
        op.drop_index("ix_dead_letter_events_event_id", table_name="dead_letter_events")
        op.drop_table("dead_letter_events")

    if _has_table("event_consumer_checkpoint"):
        op.drop_index(
            "ix_event_consumer_checkpoint_event_id",
            table_name="event_consumer_checkpoint",
        )
        op.drop_table("event_consumer_checkpoint")

    if _has_table("event_outbox"):
        op.drop_index("ix_event_outbox_workflow_run_id", table_name="event_outbox")
        op.drop_index("ix_event_outbox_run_id", table_name="event_outbox")
        op.drop_index("ix_event_outbox_subject_type_subject_id", table_name="event_outbox")
        op.drop_index("ix_event_outbox_correlation_id", table_name="event_outbox")
        op.drop_index("ix_event_outbox_status_available_at", table_name="event_outbox")
        op.drop_table("event_outbox")
