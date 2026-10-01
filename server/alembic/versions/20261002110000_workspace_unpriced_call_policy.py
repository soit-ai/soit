"""Workspace policy for calls no price applies to.

``workspaces.unpriced_call_policy`` decides what happens to a model or tool
call whose target has no price configured, so its cost would be recorded
without an amount and count against no budget: ``allow`` (NULL, the behaviour
so far), ``refuse_when_budgeted`` (refused while a hard-stop budget applies to
the call) or ``refuse``. Nullable; existing workspaces keep allowing.

Revision ID: 20261002110000
Revises: 20261002100000
Create Date: 2026-10-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261002110000"
down_revision: str | Sequence[str] | None = "20261002100000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("workspaces") as batch:
        batch.add_column(sa.Column("unpriced_call_policy", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("workspaces") as batch:
        batch.drop_column("unpriced_call_policy")
