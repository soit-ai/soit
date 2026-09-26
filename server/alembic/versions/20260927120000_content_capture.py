"""Content capture: a workspace mode that keeps run text out of the database.

``workspaces.content_capture`` is ``full`` for every existing workspace, so
nothing changes until an admin chooses ``metadata_only``.
``api_keys.content_capture`` lets one key ask for ``metadata_only`` on its
own calls; null follows the workspace.

Revision ID: 20260927120000
Revises: 20260927110000
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260927120000"
down_revision: str | Sequence[str] | None = "20260927110000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("content_capture", sa.String(), nullable=False, server_default="full"),
    )
    op.add_column("api_keys", sa.Column("content_capture", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("api_keys", "content_capture")
    op.drop_column("workspaces", "content_capture")
