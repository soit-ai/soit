"""add run subject fields

Revision ID: 20260307123000_run_subject_fields
Revises: 20260307100000_capability_governance_tables
Create Date: 2026-03-07 12:30:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260307123000_run_subject_fields"
down_revision = "20260307100000_capability_governance_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("runs")}
    indexes = {index["name"] for index in inspector.get_indexes("runs")}

    if "subject_kind" not in columns:
        op.add_column("runs", sa.Column("subject_kind", sa.String(), nullable=True))
    if "subject_id" not in columns:
        op.add_column("runs", sa.Column("subject_id", sa.String(), nullable=True))
    if "subject_version_id" not in columns:
        op.add_column("runs", sa.Column("subject_version_id", sa.String(), nullable=True))

    op.alter_column("runs", "app_id", existing_type=sa.String(), nullable=True)
    op.alter_column("runs", "app_version_id", existing_type=sa.String(), nullable=True)

    if "ix_runs_subject_kind" not in indexes:
        op.create_index("ix_runs_subject_kind", "runs", ["subject_kind"])
    if "ix_runs_subject_id" not in indexes:
        op.create_index("ix_runs_subject_id", "runs", ["subject_id"])
    if "ix_runs_subject_version_id" not in indexes:
        op.create_index("ix_runs_subject_version_id", "runs", ["subject_version_id"])
    if "ix_runs_scope_subject_started" not in indexes:
        op.create_index(
            "ix_runs_scope_subject_started",
            "runs",
            ["tenant_id", "workspace_id", "subject_kind", "subject_id", "started_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("runs")}
    columns = {column["name"] for column in inspector.get_columns("runs")}

    if "ix_runs_scope_subject_started" in indexes:
        op.drop_index("ix_runs_scope_subject_started", table_name="runs")
    if "ix_runs_subject_version_id" in indexes:
        op.drop_index("ix_runs_subject_version_id", table_name="runs")
    if "ix_runs_subject_id" in indexes:
        op.drop_index("ix_runs_subject_id", table_name="runs")
    if "ix_runs_subject_kind" in indexes:
        op.drop_index("ix_runs_subject_kind", table_name="runs")

    if "subject_version_id" in columns:
        op.drop_column("runs", "subject_version_id")
    if "subject_id" in columns:
        op.drop_column("runs", "subject_id")
    if "subject_kind" in columns:
        op.drop_column("runs", "subject_kind")

    op.alter_column("runs", "app_version_id", existing_type=sa.String(), nullable=False)
    op.alter_column("runs", "app_id", existing_type=sa.String(), nullable=False)
