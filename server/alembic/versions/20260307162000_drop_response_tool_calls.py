"""drop response tool_calls table

Revision ID: 20260307162000_drop_response_tool_calls
Revises: 20260307153000_responses_api_foundation
Create Date: 2026-03-07 16:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260307162000_drop_response_tool_calls"
down_revision = "20260307153000_responses_api_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "tool_calls" not in tables:
        return
    indexes = {index["name"] for index in inspector.get_indexes("tool_calls")}
    if "ix_tool_calls_run_status" in indexes:
        op.drop_index("ix_tool_calls_run_status", table_name="tool_calls")
    if "ix_tool_calls_response_created" in indexes:
        op.drop_index("ix_tool_calls_response_created", table_name="tool_calls")
    op.drop_table("tool_calls")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "tool_calls" in tables:
        return
    op.create_table(
        "tool_calls",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("response_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("step_id", sa.String(), nullable=True),
        sa.Column("thread_id", sa.String(), nullable=True),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("agent_id", sa.String(), nullable=True),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("tool_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("arguments_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tool_calls_response_created", "tool_calls", ["response_id", "created_at"])
    op.create_index("ix_tool_calls_run_status", "tool_calls", ["run_id", "status"])
