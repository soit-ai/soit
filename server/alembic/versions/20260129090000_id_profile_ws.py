"""add user profile and workspace metadata columns

Revision ID: 20260129090000_id_profile_ws
Revises: 20260128090000_modelhub_refactor
Create Date: 2026-01-29 09:00:00
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260129090000_id_profile_ws"
down_revision = "20260128090000_modelhub_refactor"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _has_column("users", "profile_json"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.add_column(sa.Column("profile_json", sa.JSON(), nullable=True))

    if not _has_column("workspaces", "metadata_json"):
        with op.batch_alter_table("workspaces") as batch_op:
            batch_op.add_column(sa.Column("metadata_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    if _has_column("workspaces", "metadata_json"):
        with op.batch_alter_table("workspaces") as batch_op:
            batch_op.drop_column("metadata_json")

    if _has_column("users", "profile_json"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("profile_json")
