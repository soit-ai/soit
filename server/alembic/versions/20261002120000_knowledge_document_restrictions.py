"""Knowledge document restrictions: documents only some readers of a base may read.

``knowledge_document_restrictions`` holds one row per restricted document of a
knowledge base, keyed by its ``doc_key`` so every version stays restricted. A
restricted document is readable by the workspace's Owners and Admins, the
base's creator and holders of a ``knowledge_document`` grant with ``read``.
A new table; nothing existing changes, and no document is restricted.

Revision ID: 20261002120000
Revises: 20261002110000
Create Date: 2026-10-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261002120000"
down_revision: str | Sequence[str] | None = "20261002110000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "knowledge_document_restrictions"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("knowledge_id", sa.String(), nullable=False),
        sa.Column("doc_key", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(f"ix_{TABLE}_knowledge_id", TABLE, ["knowledge_id"])
    op.create_index(
        "uq_knowledge_document_restrictions_doc",
        TABLE,
        ["tenant_id", "workspace_id", "knowledge_id", "doc_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_knowledge_document_restrictions_doc", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_knowledge_id", table_name=TABLE)
    op.drop_table(TABLE)
