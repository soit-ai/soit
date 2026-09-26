"""API key tool allowlist: which tools a key may invoke.

``api_keys.allowed_tools_json`` lists the tool refs a key may invoke, through
the tool invocation API, the MCP endpoint, or a run the key starts. Null, the
value every existing key gets, allows every tool of the workspace.

Revision ID: 20260927180000
Revises: 20260927170000
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927180000"
down_revision: str | Sequence[str] | None = "20260927170000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("allowed_tools_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("api_keys", "allowed_tools_json")
