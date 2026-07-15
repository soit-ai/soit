"""Unify runtime lineage, audit, response, and metering contracts.

Revision ID: 20260716090000
Revises: 20260715110000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260716090000"
down_revision: str | None = "20260715110000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("request_id", sa.String(), nullable=True))
    op.add_column("runs", sa.Column("parent_run_id", sa.String(), nullable=True))
    op.add_column("runs", sa.Column("source_run_id", sa.String(), nullable=True))
    op.add_column("runs", sa.Column("attempt_no", sa.Integer(), server_default="1", nullable=False))
    op.create_index("ix_runs_request_id", "runs", ["request_id"])
    op.create_index("ix_runs_parent_run_id", "runs", ["parent_run_id"])
    op.create_index("ix_runs_source_run_id", "runs", ["source_run_id"])
    op.create_index(
        "ix_runs_scope_parent_created",
        "runs",
        ["tenant_id", "workspace_id", "parent_run_id", "created_at"],
    )
    op.create_index(
        "ix_runs_scope_source_created",
        "runs",
        ["tenant_id", "workspace_id", "source_run_id", "created_at"],
    )
    op.create_index(
        "ix_runs_scope_request_created",
        "runs",
        ["tenant_id", "workspace_id", "request_id", "created_at"],
    )

    op.add_column("responses", sa.Column("request_id", sa.String(), nullable=True))
    op.create_index("ix_responses_request_id", "responses", ["request_id"])
    op.create_index(
        "ix_responses_scope_request_created",
        "responses",
        ["tenant_id", "workspace_id", "request_id", "created_at"],
    )
    op.execute("UPDATE responses SET status = 'running' WHERE status = 'in_progress'")
    op.execute("UPDATE responses SET status = 'succeeded' WHERE status = 'completed'")
    op.execute(
        "UPDATE response_events SET type = 'response.output_text.done' "
        "WHERE type = 'response.output_text.completed'"
    )
    op.execute("UPDATE response_events SET type = 'response.succeeded' WHERE type = 'response.completed'")

    op.add_column(
        "run_cost_entries",
        sa.Column("entry_type", sa.String(), server_default="usage", nullable=False),
    )
    op.create_index("ix_run_cost_entries_entry_type", "run_cost_entries", ["entry_type"])
    op.execute(
        "UPDATE run_cost_entries SET entry_type = "
        "CASE WHEN amount > 0 THEN 'charge' ELSE 'usage' END"
    )
    op.alter_column("run_cost_entries", "currency", existing_type=sa.String(), nullable=True)
    op.alter_column(
        "run_cost_entries",
        "amount",
        existing_type=sa.Numeric(18, 6),
        nullable=True,
    )
    op.execute("UPDATE run_cost_entries SET currency = NULL, amount = NULL WHERE entry_type = 'usage'")

    op.add_column("audit_events", sa.Column("run_id", sa.String(), nullable=True))
    op.add_column("audit_events", sa.Column("step_id", sa.String(), nullable=True))
    op.add_column("audit_events", sa.Column("trace_id", sa.String(), nullable=True))
    op.add_column("audit_events", sa.Column("outcome", sa.String(), nullable=True))
    op.add_column("audit_events", sa.Column("evidence_artifact_id", sa.String(), nullable=True))
    for column in ("run_id", "step_id", "trace_id", "outcome", "evidence_artifact_id"):
        op.create_index(f"ix_audit_events_{column}", "audit_events", [column])
    op.create_index(
        "ix_audit_events_scope_run_created",
        "audit_events",
        ["tenant_id", "workspace_id", "run_id", "created_at"],
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text(
                """
                INSERT INTO audit_events (
                    id, tenant_id, workspace_id, event_type, resource_type,
                    resource_id, run_id, step_id, trace_id, outcome,
                    operation, actor_user_id, scope, payload_json, created_at
                )
                SELECT
                    'audit_backfill_' || rs.id,
                    rs.tenant_id,
                    rs.workspace_id,
                    'gateway.request',
                    COALESCE((rs.metrics_json ->> 'audit_json')::jsonb ->> 'gateway_type', rs.step_type),
                    rs.id,
                    rs.run_id,
                    rs.id,
                    rs.trace_id,
                    CASE WHEN rs.status = 'failed' THEN 'failed' ELSE 'succeeded' END,
                    'invoke',
                    NULL,
                    'workspace',
                    CASE
                        WHEN rs.metrics_json::jsonb ? 'audit_json'
                            THEN (rs.metrics_json ->> 'audit_json')::jsonb
                        ELSE jsonb_build_object(
                            'gateway_type', rs.step_type,
                            'preview', rs.metrics_json ->> 'audit_preview',
                            'artifact_key', rs.metrics_json ->> 'audit_artifact',
                            'truncated', COALESCE((rs.metrics_json ->> 'audit_truncated')::boolean, false),
                            'audit_size', rs.metrics_json ->> 'audit_size'
                        )
                    END,
                    rs.created_at
                FROM run_steps rs
                WHERE rs.metrics_json IS NOT NULL
                  AND (
                    rs.metrics_json::jsonb ? 'audit_json'
                    OR rs.metrics_json::jsonb ? 'audit_preview'
                    OR rs.metrics_json::jsonb ? 'audit_artifact'
                  )
                ON CONFLICT (id) DO NOTHING
                """
            )
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DELETE FROM audit_events WHERE id LIKE 'audit_backfill_%'")

    op.drop_index("ix_audit_events_scope_run_created", table_name="audit_events")
    for column in reversed(("run_id", "step_id", "trace_id", "outcome", "evidence_artifact_id")):
        op.drop_index(f"ix_audit_events_{column}", table_name="audit_events")
        op.drop_column("audit_events", column)

    op.execute("UPDATE run_cost_entries SET currency = 'USD', amount = 0 WHERE entry_type = 'usage'")
    op.alter_column(
        "run_cost_entries",
        "amount",
        existing_type=sa.Numeric(18, 6),
        nullable=False,
    )
    op.alter_column("run_cost_entries", "currency", existing_type=sa.String(), nullable=False)
    op.drop_index("ix_run_cost_entries_entry_type", table_name="run_cost_entries")
    op.drop_column("run_cost_entries", "entry_type")

    op.execute("UPDATE response_events SET type = 'response.completed' WHERE type = 'response.succeeded'")
    op.execute(
        "UPDATE response_events SET type = 'response.output_text.completed' "
        "WHERE type = 'response.output_text.done'"
    )
    op.execute("UPDATE responses SET status = 'completed' WHERE status = 'succeeded'")
    op.execute("UPDATE responses SET status = 'in_progress' WHERE status = 'running'")
    op.drop_index("ix_responses_scope_request_created", table_name="responses")
    op.drop_index("ix_responses_request_id", table_name="responses")
    op.drop_column("responses", "request_id")

    op.drop_index("ix_runs_scope_request_created", table_name="runs")
    op.drop_index("ix_runs_scope_source_created", table_name="runs")
    op.drop_index("ix_runs_scope_parent_created", table_name="runs")
    op.drop_index("ix_runs_source_run_id", table_name="runs")
    op.drop_index("ix_runs_parent_run_id", table_name="runs")
    op.drop_index("ix_runs_request_id", table_name="runs")
    op.drop_column("runs", "attempt_no")
    op.drop_column("runs", "source_run_id")
    op.drop_column("runs", "parent_run_id")
    op.drop_column("runs", "request_id")
