"""Add notification preferences, endpoints, and deliveries.

Revision ID: 20260715100000
Revises: 20260715090000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260715100000"
down_revision: str | None = "20260715090000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("delivery_mode", sa.String(length=32), nullable=False),
        sa.Column("categories_json", sa.JSON(), nullable=False),
        sa.Column("quiet_hours_enabled", sa.Boolean(), nullable=False),
        sa.Column("quiet_hours_start", sa.String(length=5), nullable=False),
        sa.Column("quiet_hours_end", sa.String(length=5), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notification_preferences_tenant_id", "notification_preferences", ["tenant_id"])
    op.create_index("ix_notification_preferences_workspace_id", "notification_preferences", ["workspace_id"])
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"])

    op.create_table(
        "notification_endpoints",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("secret_ref", sa.String(length=256), nullable=False),
        sa.Column("display_target", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("tenant_id", "workspace_id", "user_id", "kind", "status"):
        op.create_index(f"ix_notification_endpoints_{column}", "notification_endpoints", [column])

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("notification_id", sa.String(), nullable=False),
        sa.Column("endpoint_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "tenant_id",
        "workspace_id",
        "user_id",
        "notification_id",
        "endpoint_id",
        "status",
        "available_at",
    ):
        op.create_index(f"ix_notification_deliveries_{column}", "notification_deliveries", [column])


def downgrade() -> None:
    op.drop_table("notification_deliveries")
    op.drop_table("notification_endpoints")
    op.drop_table("notification_preferences")
