"""Add saved views and pinned objects.

Revision ID: 20260830130000
Revises: 20260830120000
Create Date: 2026-08-30 13:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260830130000"
down_revision: Union[str, Sequence[str], None] = "20260830120000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VIEWS = "saved_views"
PINS = "pinned_objects"


def upgrade() -> None:
    op.create_table(
        VIEWS,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("surface", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        # The console's own query string. Parsing it into columns would tie the
        # schema to whichever filters a screen happens to offer today.
        sa.Column("query", sa.String(length=2048), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "workspace_id",
            "user_id",
            "surface",
            "name",
            name="uq_saved_view_name",
        ),
    )
    op.create_index(f"ix_{VIEWS}_tenant_id", VIEWS, ["tenant_id"])
    op.create_index(f"ix_{VIEWS}_workspace_id", VIEWS, ["workspace_id"])
    op.create_index(f"ix_{VIEWS}_user_id", VIEWS, ["user_id"])
    op.create_index(f"ix_{VIEWS}_surface", VIEWS, ["surface"])
    op.create_index("ix_saved_views_owner", VIEWS, ["workspace_id", "user_id", "surface"])

    op.create_table(
        PINS,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column("object_id", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "workspace_id",
            "user_id",
            "object_type",
            "object_id",
            name="uq_pinned_object",
        ),
    )
    op.create_index(f"ix_{PINS}_tenant_id", PINS, ["tenant_id"])
    op.create_index(f"ix_{PINS}_workspace_id", PINS, ["workspace_id"])
    op.create_index(f"ix_{PINS}_user_id", PINS, ["user_id"])
    op.create_index(f"ix_{PINS}_object_type", PINS, ["object_type"])
    op.create_index(f"ix_{PINS}_object_id", PINS, ["object_id"])
    op.create_index("ix_pinned_objects_owner", PINS, ["workspace_id", "user_id"])


def downgrade() -> None:
    op.drop_index("ix_pinned_objects_owner", table_name=PINS)
    op.drop_index(f"ix_{PINS}_object_id", table_name=PINS)
    op.drop_index(f"ix_{PINS}_object_type", table_name=PINS)
    op.drop_index(f"ix_{PINS}_user_id", table_name=PINS)
    op.drop_index(f"ix_{PINS}_workspace_id", table_name=PINS)
    op.drop_index(f"ix_{PINS}_tenant_id", table_name=PINS)
    op.drop_table(PINS)

    op.drop_index("ix_saved_views_owner", table_name=VIEWS)
    op.drop_index(f"ix_{VIEWS}_surface", table_name=VIEWS)
    op.drop_index(f"ix_{VIEWS}_user_id", table_name=VIEWS)
    op.drop_index(f"ix_{VIEWS}_workspace_id", table_name=VIEWS)
    op.drop_index(f"ix_{VIEWS}_tenant_id", table_name=VIEWS)
    op.drop_table(VIEWS)
