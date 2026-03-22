"""add workflow core tables

Revision ID: 20260306143000_workflow_core_tables
Revises: 20260306113000_runtime_thread_task_tables
Create Date: 2026-03-06 14:30:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260306143000_workflow_core_tables"
down_revision = "20260306113000_runtime_thread_task_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "workflows" not in tables:
        op.create_table(
            "workflows",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("visibility", sa.String(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("current_version_id", sa.String(), nullable=True),
            sa.Column("published_version_id", sa.String(), nullable=True),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("updated_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_workflows_tenant_workspace_status", "workflows", ["tenant_id", "workspace_id", "status"])
        op.create_index("ix_workflows_tenant_workspace_name", "workflows", ["tenant_id", "workspace_id", "name"])

    if "workflow_versions" not in tables:
        op.create_table(
            "workflow_versions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("workflow_id", sa.String(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("spec_schema", sa.String(), nullable=False),
            sa.Column("spec_json", sa.JSON(), nullable=False),
            sa.Column("created_from_version_id", sa.String(), nullable=True),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
            sa.UniqueConstraint("workflow_id", "version", name="uq_workflow_versions_workflow_id_version"),
        )
        op.create_index("ix_workflow_versions_workflow_id_status", "workflow_versions", ["workflow_id", "status"])

    if "workflow_publishes" not in tables:
        op.create_table(
            "workflow_publishes",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("workflow_id", sa.String(), nullable=False),
            sa.Column("workflow_version_id", sa.String(), nullable=False),
            sa.Column("scope", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"]),
            sa.ForeignKeyConstraint(["workflow_version_id"], ["workflow_versions.id"]),
        )
        op.create_index("ix_workflow_publishes_workflow_id", "workflow_publishes", ["workflow_id"])
        op.create_index("ix_workflow_publishes_version_id", "workflow_publishes", ["workflow_version_id"])


def downgrade() -> None:
    op.drop_index("ix_workflow_publishes_version_id", table_name="workflow_publishes")
    op.drop_index("ix_workflow_publishes_workflow_id", table_name="workflow_publishes")
    op.drop_table("workflow_publishes")

    op.drop_index("ix_workflow_versions_workflow_id_status", table_name="workflow_versions")
    op.drop_table("workflow_versions")

    op.drop_index("ix_workflows_tenant_workspace_name", table_name="workflows")
    op.drop_index("ix_workflows_tenant_workspace_status", table_name="workflows")
    op.drop_table("workflows")
