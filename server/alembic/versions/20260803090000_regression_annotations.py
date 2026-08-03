"""Record human verdicts on regression cases.

Revision ID: 20260803090000
Revises: 20260731100000
Create Date: 2026-08-03 09:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260803090000"
down_revision: Union[str, Sequence[str], None] = "20260731100000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ANNOTATIONS = "regression_annotations"


def upgrade() -> None:
    op.create_table(
        ANNOTATIONS,
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("case_id", sa.String(), nullable=False),
        sa.Column("report_id", sa.String(), nullable=True),
        sa.Column("verdict", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=False, server_default=""),
        sa.Column("annotated_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(f"ix_{ANNOTATIONS}_tenant_id", ANNOTATIONS, ["tenant_id"])
    op.create_index(f"ix_{ANNOTATIONS}_workspace_id", ANNOTATIONS, ["workspace_id"])
    op.create_index(f"ix_{ANNOTATIONS}_case_id", ANNOTATIONS, ["case_id"])
    op.create_index(f"ix_{ANNOTATIONS}_verdict", ANNOTATIONS, ["verdict"])
    op.create_index(f"ix_{ANNOTATIONS}_created_at", ANNOTATIONS, ["created_at"])
    op.create_index(
        f"ix_{ANNOTATIONS}_case", ANNOTATIONS, ["tenant_id", "workspace_id", "case_id"]
    )
    op.create_index(f"ix_{ANNOTATIONS}_report", ANNOTATIONS, ["report_id"])


def downgrade() -> None:
    op.drop_index(f"ix_{ANNOTATIONS}_report", table_name=ANNOTATIONS)
    op.drop_index(f"ix_{ANNOTATIONS}_case", table_name=ANNOTATIONS)
    op.drop_index(f"ix_{ANNOTATIONS}_created_at", table_name=ANNOTATIONS)
    op.drop_index(f"ix_{ANNOTATIONS}_verdict", table_name=ANNOTATIONS)
    op.drop_index(f"ix_{ANNOTATIONS}_case_id", table_name=ANNOTATIONS)
    op.drop_index(f"ix_{ANNOTATIONS}_workspace_id", table_name=ANNOTATIONS)
    op.drop_index(f"ix_{ANNOTATIONS}_tenant_id", table_name=ANNOTATIONS)
    op.drop_table(ANNOTATIONS)
