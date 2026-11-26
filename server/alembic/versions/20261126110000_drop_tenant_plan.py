"""Drop the plan column from tenants.

Plans, subscriptions and billing belong to the cloud control plane, which
grants a runtime its features through entitlements. The runtime never read
``tenants.plan``; it was a free-text label that every tenant carried as
``free``.

Revision ID: 20261126110000
Revises: 20261126100000
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261126110000"
down_revision: str | Sequence[str] | None = "20261126100000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("tenants", "plan")


def downgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("plan", sa.String(), nullable=False, server_default="free"),
    )
