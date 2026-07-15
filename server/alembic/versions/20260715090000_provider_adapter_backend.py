"""Add provider adapter backend.

Revision ID: 20260715090000
Revises: 20260714120000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260715090000"
down_revision: str | None = "20260714120000_outbox_workspace_leases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "providers",
        sa.Column("adapter_backend", sa.String(), nullable=False, server_default="native"),
    )
    op.create_index(
        op.f("ix_providers_adapter_backend"),
        "providers",
        ["adapter_backend"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_providers_adapter_backend"), table_name="providers")
    op.drop_column("providers", "adapter_backend")
