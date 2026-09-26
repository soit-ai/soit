"""Sealed secret values: a Vault-free secrets backend for evaluation installs.

Adds `sealed_secret_values`, read and written only when
`SECRETS_BACKEND=sealed`. Existing deployments keep using Vault and never
touch the table.

Revision ID: 20260926110000
Revises: 20260926100000
Create Date: 2026-09-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260926110000"
down_revision: str | Sequence[str] | None = "20260926100000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sealed_secret_values",
        sa.Column("locator", sa.String(length=512), primary_key=True),
        sa.Column("sealed_value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sealed_secret_values")