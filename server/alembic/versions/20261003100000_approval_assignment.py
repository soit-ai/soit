"""Approval assignment and deadlines: who may decide a request, by when, and its history.

``approval_requests`` gains ``assignee_user_ids`` and ``assignee_roles`` (who
may decide; both empty keeps today's rule, any member who can write) and
``expires_at`` (when a request nobody decided closes as ``expired``).
``approval_decisions`` records every decision, closing and delegation of a
request, added to and never changed. Existing requests stay unassigned and
never expire.

Revision ID: 20261003100000
Revises: 20261002120000
Create Date: 2026-10-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261003100000"
down_revision: str | Sequence[str] | None = "20261002120000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REQUESTS = "approval_requests"
DECISIONS = "approval_decisions"


def upgrade() -> None:
    with op.batch_alter_table(REQUESTS) as batch:
        batch.add_column(sa.Column("assignee_user_ids", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("assignee_roles", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.create_index(f"ix_{REQUESTS}_expires_at", REQUESTS, ["expires_at"])

    op.create_table(
        DECISIONS,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("approval_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=True),
        sa.Column("actor_role", sa.String(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("assignees_before_json", sa.JSON(), nullable=True),
        sa.Column("assignees_after_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(f"ix_{DECISIONS}_tenant_id", DECISIONS, ["tenant_id"])
    op.create_index(f"ix_{DECISIONS}_workspace_id", DECISIONS, ["workspace_id"])
    op.create_index("ix_approval_decisions_approval", DECISIONS, ["approval_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_approval_decisions_approval", table_name=DECISIONS)
    op.drop_index(f"ix_{DECISIONS}_workspace_id", table_name=DECISIONS)
    op.drop_index(f"ix_{DECISIONS}_tenant_id", table_name=DECISIONS)
    op.drop_table(DECISIONS)
    op.drop_index(f"ix_{REQUESTS}_expires_at", table_name=REQUESTS)
    with op.batch_alter_table(REQUESTS) as batch:
        batch.drop_column("expires_at")
        batch.drop_column("assignee_roles")
        batch.drop_column("assignee_user_ids")
