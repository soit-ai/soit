"""Approval self-approval switch and reminders before a request's deadline.

``workspaces.forbid_self_approval``: when true, whoever opened an approval
request cannot approve it (null or false allows it, as before).
``approval_requests.remind_at``: when the approvers of an undecided request
are reminded of its deadline; cleared once they are. Existing workspaces keep
allowing self-approval, and existing requests are not reminded.

Revision ID: 20261003110000
Revises: 20261003100000
Create Date: 2026-10-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261003110000"
down_revision: str | Sequence[str] | None = "20261003100000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("workspaces") as batch:
        batch.add_column(sa.Column("forbid_self_approval", sa.Boolean(), nullable=True))
    with op.batch_alter_table("approval_requests") as batch:
        batch.add_column(sa.Column("remind_at", sa.DateTime(), nullable=True))
    op.create_index("ix_approval_requests_remind_at", "approval_requests", ["remind_at"])


def downgrade() -> None:
    op.drop_index("ix_approval_requests_remind_at", table_name="approval_requests")
    with op.batch_alter_table("approval_requests") as batch:
        batch.drop_column("remind_at")
    with op.batch_alter_table("workspaces") as batch:
        batch.drop_column("forbid_self_approval")
