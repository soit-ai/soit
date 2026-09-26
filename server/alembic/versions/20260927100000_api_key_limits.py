"""Per-key limits for API keys: rate, daily requests and tokens, addresses, models.

Every column is nullable and null means "no limit of this kind", so existing
keys keep working exactly as before.

Revision ID: 20260927100000
Revises: 20260926110000
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927100000"
down_revision: str | Sequence[str] | None = "20260926110000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "api_keys"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("rate_limit_per_minute", sa.Integer(), nullable=True))
    op.add_column(TABLE, sa.Column("daily_request_quota", sa.Integer(), nullable=True))
    op.add_column(TABLE, sa.Column("daily_token_quota", sa.Integer(), nullable=True))
    op.add_column(TABLE, sa.Column("ip_allowlist_json", sa.JSON(), nullable=True))
    op.add_column(TABLE, sa.Column("allowed_models_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column(TABLE, "allowed_models_json")
    op.drop_column(TABLE, "ip_allowlist_json")
    op.drop_column(TABLE, "daily_token_quota")
    op.drop_column(TABLE, "daily_request_quota")
    op.drop_column(TABLE, "rate_limit_per_minute")
