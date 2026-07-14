"""add parent_id to chat messages for branch threading

Revision ID: 20260211170000_message_parent_id
Revises: 20260129090000_id_profile_ws
Create Date: 2026-02-11 17:00:00
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260211170000_message_parent_id"
down_revision = "20260129090000_id_profile_ws"
branch_labels = None
depends_on = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in set(_inspector().get_table_names())


def _has_column(table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in _inspector().get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in _inspector().get_indexes(table_name)}


def upgrade() -> None:
    if not _has_table("messages"):
        return
    if not _has_column("messages", "parent_id"):
        op.add_column("messages", sa.Column("parent_id", sa.String(), nullable=True))
    if not _has_index("messages", "ix_messages_parent_id"):
        op.create_index(op.f("ix_messages_parent_id"), "messages", ["parent_id"], unique=False)


def downgrade() -> None:
    if not _has_table("messages"):
        return
    inspector = _inspector()
    fk_names = {
        fk["name"]
        for fk in inspector.get_foreign_keys("messages")
        if fk.get("name")
    }
    if "fk_messages_parent_id_messages" in fk_names:
        op.drop_constraint("fk_messages_parent_id_messages", "messages", type_="foreignkey")
    if _has_index("messages", "ix_messages_parent_id"):
        op.drop_index(op.f("ix_messages_parent_id"), table_name="messages")
    if _has_column("messages", "parent_id"):
        op.drop_column("messages", "parent_id")
