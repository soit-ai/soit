"""Repair schema objects that pre-baseline databases never received.

The 20260718140000 fresh-install baseline squashed history and is the only
revision that creates the product_feedbacks table and the
agent_publishes.sequence column. Databases created before the squash and
stamped onto the baseline chain therefore miss both objects and fail at
runtime (feedback endpoints and publish history 500). This revision creates
them idempotently; fresh installs already have the objects and skip every
step.

Revision ID: 20260806160000
Revises: 20260803090000
Create Date: 2026-08-06 16:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260806160000"
down_revision: Union[str, Sequence[str], None] = "20260803090000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FEEDBACKS = "product_feedbacks"
PUBLISHES = "agent_publishes"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if FEEDBACKS not in tables:
        op.create_table(
            FEEDBACKS,
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("tenant_id", sa.String(length=64), nullable=False),
            sa.Column("workspace_id", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("category", sa.String(length=32), nullable=False),
            sa.Column("priority", sa.String(length=32), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("context_json", sa.JSON(), nullable=False),
            sa.Column("created_by", sa.String(length=64), nullable=False),
            sa.Column("updated_by", sa.String(length=64), nullable=False),
            sa.Column("resolved_by", sa.String(length=64), nullable=True),
            sa.Column("resolution_note", sa.Text(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(f"ix_{FEEDBACKS}_category", FEEDBACKS, ["category"])
        op.create_index(f"ix_{FEEDBACKS}_created_by", FEEDBACKS, ["created_by"])
        op.create_index(f"ix_{FEEDBACKS}_priority", FEEDBACKS, ["priority"])
        op.create_index(
            f"ix_{FEEDBACKS}_scope_created",
            FEEDBACKS,
            ["tenant_id", "workspace_id", "created_at"],
        )
        op.create_index(
            f"ix_{FEEDBACKS}_scope_creator",
            FEEDBACKS,
            ["tenant_id", "workspace_id", "created_by"],
        )
        op.create_index(
            f"ix_{FEEDBACKS}_scope_status_priority",
            FEEDBACKS,
            ["tenant_id", "workspace_id", "status", "priority"],
        )
        op.create_index(f"ix_{FEEDBACKS}_status", FEEDBACKS, ["status"])
        op.create_index(f"ix_{FEEDBACKS}_tenant_id", FEEDBACKS, ["tenant_id"])
        op.create_index(f"ix_{FEEDBACKS}_workspace_id", FEEDBACKS, ["workspace_id"])

    if PUBLISHES in tables:
        columns = {column["name"] for column in inspector.get_columns(PUBLISHES)}
        if "sequence" not in columns:
            op.add_column(
                PUBLISHES, sa.Column("sequence", sa.Integer(), nullable=True)
            )
            op.execute(
                """
                UPDATE agent_publishes
                SET sequence = numbered.seq
                FROM (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY tenant_id, workspace_id, agent_id
                        ORDER BY created_at, id
                    ) AS seq
                    FROM agent_publishes
                ) AS numbered
                WHERE agent_publishes.id = numbered.id
                """
            )
            op.alter_column(PUBLISHES, "sequence", nullable=False)
            op.create_unique_constraint(
                "uq_agent_publishes_scope_sequence",
                PUBLISHES,
                ["tenant_id", "workspace_id", "agent_id", "sequence"],
            )


def downgrade() -> None:
    # The repaired objects are part of the baseline schema, so removing them
    # would break fresh installs that never ran this repair. Intentional no-op.
    pass
