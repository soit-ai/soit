"""Workspace PII actions: what content safety does with personal data here.

``workspaces.pii_action_inbound`` and ``pii_action_outbound`` override the
deployment's ``CONTENT_SAFETY_PII_ACTION`` for content entering and leaving
the runtime in one workspace (``observe``, ``redact`` or ``block``). Null, the
value every existing workspace gets, follows the deployment.

Revision ID: 20260927170000
Revises: 20260927160000
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927170000"
down_revision: str | Sequence[str] | None = "20260927160000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("pii_action_inbound", sa.String(), nullable=True))
    op.add_column("workspaces", sa.Column("pii_action_outbound", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("workspaces", "pii_action_outbound")
    op.drop_column("workspaces", "pii_action_inbound")
