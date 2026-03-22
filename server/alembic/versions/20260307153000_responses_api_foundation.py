"""add responses api foundation tables

Revision ID: 20260307153000_responses_api_foundation
Revises: 20260307143000_drop_run_app_foreign_keys
Create Date: 2026-03-07 15:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260307153000_responses_api_foundation"
down_revision = "20260307143000_drop_run_app_foreign_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "responses" not in tables:
        op.create_table(
            "responses",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("thread_id", sa.String(), nullable=True),
            sa.Column("task_id", sa.String(), nullable=True),
            sa.Column("agent_id", sa.String(), nullable=True),
            sa.Column("run_id", sa.String(), nullable=True),
            sa.Column("model", sa.String(), nullable=True),
            sa.Column("provider", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("input_json", sa.JSON(), nullable=False),
            sa.Column("output_json", sa.JSON(), nullable=False),
            sa.Column("usage_json", sa.JSON(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.Column("error_code", sa.String(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("updated_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("canceled_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["thread_id"], ["threads.id"]),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
            sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        )
        op.create_index(
            "ix_responses_scope_status_created",
            "responses",
            ["tenant_id", "workspace_id", "status", "created_at"],
        )
        op.create_index("ix_responses_thread_created", "responses", ["thread_id", "created_at"])
        op.create_index("ix_responses_agent_created", "responses", ["agent_id", "created_at"])
        op.create_index("ix_responses_run_id", "responses", ["run_id"])

    if "response_events" not in tables:
        op.create_table(
            "response_events",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("response_id", sa.String(), nullable=False),
            sa.Column("run_id", sa.String(), nullable=True),
            sa.Column("thread_id", sa.String(), nullable=True),
            sa.Column("task_id", sa.String(), nullable=True),
            sa.Column("agent_id", sa.String(), nullable=True),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(), nullable=False),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["response_id"], ["responses.id"]),
            sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
            sa.ForeignKeyConstraint(["thread_id"], ["threads.id"]),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
            sa.UniqueConstraint("response_id", "sequence", name="uq_response_events_response_sequence"),
        )
        op.create_index("ix_response_events_response_created", "response_events", ["response_id", "created_at"])
        op.create_index("ix_response_events_run_created", "response_events", ["run_id", "created_at"])
        op.create_index("ix_response_events_type_created", "response_events", ["type", "created_at"])

def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "response_events" in tables:
        op.drop_index("ix_response_events_type_created", table_name="response_events")
        op.drop_index("ix_response_events_run_created", table_name="response_events")
        op.drop_index("ix_response_events_response_created", table_name="response_events")
        op.drop_table("response_events")

    if "responses" in tables:
        op.drop_index("ix_responses_run_id", table_name="responses")
        op.drop_index("ix_responses_agent_created", table_name="responses")
        op.drop_index("ix_responses_thread_created", table_name="responses")
        op.drop_index("ix_responses_scope_status_created", table_name="responses")
        op.drop_table("responses")
