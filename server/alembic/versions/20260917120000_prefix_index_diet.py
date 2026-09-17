"""Index diet: drop single-column indexes that are left prefixes of a composite one.

Every row written on the execution path maintained one B-tree per index; the
indexes dropped here never served a query the composite next to them cannot
serve from its leading column.

Revision ID: 20260917120000
Revises: 20260917100000
Create Date: 2026-09-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260917120000"
down_revision: str | Sequence[str] | None = "20260917100000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, index, column) -> the composite index whose first column covers it
_REDUNDANT: list[tuple[str, str, str]] = [
    ("runs", "ix_runs_tenant_id", "tenant_id"),  # ix_runs_scope_*
    ("run_cost_entries", "ix_run_cost_entries_tenant_id", "tenant_id"),  # uq_run_cost_entries_tenant_source_ref
    ("run_step_tool_calls", "ix_run_step_tool_calls_run_id", "run_id"),  # ix_run_step_tool_calls_run_status
    ("run_step_tool_calls", "ix_run_step_tool_calls_status", "status"),  # ix_run_step_tool_calls_lease
    ("responses", "ix_responses_tenant_id", "tenant_id"),  # ix_responses_scope_*
    ("responses", "ix_responses_thread_id", "thread_id"),  # ix_responses_thread_created
    ("responses", "ix_responses_agent_id", "agent_id"),  # ix_responses_agent_created
    ("response_events", "ix_response_events_response_id", "response_id"),  # uq_response_events_response_sequence
    ("response_events", "ix_response_events_run_id", "run_id"),  # ix_response_events_run_created
    ("response_events", "ix_response_events_interaction_id", "interaction_id"),  # ix_response_events_interaction_sequence
    ("response_events", "ix_response_events_type", "type"),  # ix_response_events_type_created
    ("response_interactions", "ix_response_interactions_response_id", "response_id"),  # ix_response_interactions_response_created
    ("response_interactions", "ix_response_interactions_run_id", "run_id"),  # ix_response_interactions_run_created
    ("response_interactions", "ix_response_interactions_tenant_id", "tenant_id"),  # uq_response_interactions_scope_interaction
    ("threads", "ix_threads_tenant_id", "tenant_id"),  # ix_threads_scope_updated
    ("threads", "ix_threads_status", "status"),  # ix_threads_status_archived
    ("threads", "ix_threads_owner_user_id", "owner_user_id"),  # ix_threads_owner_updated
    ("threads", "ix_threads_agent_id", "agent_id"),  # ix_threads_agent_status
    ("thread_messages", "ix_thread_messages_thread_id", "thread_id"),  # uq_thread_messages_thread_sequence
    ("thread_messages", "ix_thread_messages_status", "status"),  # ix_thread_messages_status_created
    ("tasks", "ix_tasks_run_id", "run_id"),  # ix_tasks_run_status
    ("tasks", "ix_tasks_agent_id", "agent_id"),  # ix_tasks_agent_status
    ("audit_events", "ix_audit_events_tenant_id", "tenant_id"),  # ix_audit_events_scope_*
    ("audit_events", "ix_audit_events_event_type", "event_type"),  # ix_audit_events_event_type_created
]


def upgrade() -> None:
    # Databases created before a given index existed must still upgrade.
    for _table, index, _column in _REDUNDANT:
        op.execute(sa.text(f"DROP INDEX IF EXISTS {index}"))


def downgrade() -> None:
    for table, index, column in reversed(_REDUNDANT):
        op.create_index(op.f(index), table, [column], unique=False)
