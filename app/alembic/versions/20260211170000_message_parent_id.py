"""add parent_id to chat messages for branch threading

Revision ID: 20260211170000_message_parent_id
Revises: 20260129090000_id_profile_ws
Create Date: 2026-02-11 17:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260211170000_message_parent_id"
down_revision = "20260129090000_id_profile_ws"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("parent_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_messages_parent_id"), "messages", ["parent_id"], unique=False)
    op.create_foreign_key(
        "fk_messages_parent_id_messages",
        "messages",
        "messages",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_messages_parent_id_messages", "messages", type_="foreignkey")
    op.drop_index(op.f("ix_messages_parent_id"), table_name="messages")
    op.drop_column("messages", "parent_id")
