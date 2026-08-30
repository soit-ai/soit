"""Add schedules.

Revision ID: 20260830180000
Revises: 20260830170000
Create Date: 2026-08-30 18:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260830180000"
down_revision: Union[str, Sequence[str], None] = "20260830170000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "schedules"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("target_kind", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("cron", sa.String(length=128), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        # Off by default: a scheduler that was down for a day would otherwise
        # wake up and fire twenty-four hourly jobs at once.
        sa.Column("catch_up", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("next_fire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_id", sa.String(), nullable=True),
        sa.Column("last_status", sa.String(length=32), nullable=True),
        sa.Column("last_error", sa.String(length=512), nullable=True),
        # Claim state, shared with every other durable worker.
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("lease_owner", sa.String(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "name", name="uq_schedule_name"),
    )
    op.create_index(f"ix_{TABLE}_tenant_id", TABLE, ["tenant_id"])
    op.create_index(f"ix_{TABLE}_workspace_id", TABLE, ["workspace_id"])
    op.create_index(f"ix_{TABLE}_target_kind", TABLE, ["target_kind"])
    op.create_index(f"ix_{TABLE}_target_id", TABLE, ["target_id"])
    op.create_index(f"ix_{TABLE}_enabled", TABLE, ["enabled"])
    op.create_index(f"ix_{TABLE}_next_fire_at", TABLE, ["next_fire_at"])
    op.create_index(f"ix_{TABLE}_last_run_id", TABLE, ["last_run_id"])
    op.create_index(f"ix_{TABLE}_status", TABLE, ["status"])
    op.create_index(f"ix_{TABLE}_lease_owner", TABLE, ["lease_owner"])
    op.create_index(f"ix_{TABLE}_lease_expires_at", TABLE, ["lease_expires_at"])
    op.create_index("ix_schedules_due", TABLE, ["status", "enabled", "next_fire_at"])
    op.create_index("ix_schedules_scope", TABLE, ["tenant_id", "workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_schedules_scope", table_name=TABLE)
    op.drop_index("ix_schedules_due", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_lease_expires_at", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_lease_owner", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_status", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_last_run_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_next_fire_at", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_enabled", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_target_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_target_kind", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_workspace_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_tenant_id", table_name=TABLE)
    op.drop_table(TABLE)
