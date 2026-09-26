"""Knowledge visibility becomes enforced: open existing knowledge bases to the workspace.

Until now ``knowledge.visibility`` was stored but never checked, and every
knowledge base created from the console received the ``private`` default, so
every member of a workspace could reach every knowledge base in it. From this
revision ``private`` means creator, workspace owners and admins, and explicit
grantees only. Existing rows move to ``workspace`` so an upgrade keeps the
access members already had; ``workspace`` is also the new default, and
``private`` becomes an explicit choice.

Revision ID: 20260926100000
Revises: 20260917120000
Create Date: 2026-09-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260926100000"
down_revision: str | Sequence[str] | None = "20260917120000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE knowledge SET visibility = 'workspace' WHERE visibility = 'private'")
    )


def downgrade() -> None:
    # The rows opened by upgrade() cannot be told apart from knowledge bases
    # made workspace-visible afterwards, and visibility is unenforced before
    # this revision, so there is nothing to restore.
    pass
