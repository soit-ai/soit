"""add capability and governance tables

Revision ID: 20260307100000_capability_governance_tables
Revises: 20260306143000_workflow_core_tables
Create Date: 2026-03-07 10:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260307100000_capability_governance_tables"
down_revision = "20260306143000_workflow_core_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "skills" not in tables:
        op.create_table(
            "skills",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("category", sa.String(), nullable=False),
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
        op.create_index("ix_skills_tenant_workspace_status", "skills", ["tenant_id", "workspace_id", "status"])
        op.create_index("ix_skills_tenant_workspace_name", "skills", ["tenant_id", "workspace_id", "name"])

    if "skill_versions" not in tables:
        op.create_table(
            "skill_versions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("skill_id", sa.String(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("spec_schema", sa.String(), nullable=False),
            sa.Column("spec_json", sa.JSON(), nullable=False),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
            sa.UniqueConstraint("skill_id", "version", name="uq_skill_versions_skill_id_version"),
        )
        op.create_index("ix_skill_versions_skill_id_status", "skill_versions", ["skill_id", "status"])

    if "skill_publishes" not in tables:
        op.create_table(
            "skill_publishes",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("skill_id", sa.String(), nullable=False),
            sa.Column("skill_version_id", sa.String(), nullable=False),
            sa.Column("scope", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
            sa.ForeignKeyConstraint(["skill_version_id"], ["skill_versions.id"]),
        )
        op.create_index("ix_skill_publishes_skill_id", "skill_publishes", ["skill_id"])
        op.create_index("ix_skill_publishes_version_id", "skill_publishes", ["skill_version_id"])

    if "mcp_servers" not in tables:
        op.create_table(
            "mcp_servers",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("transport", sa.String(), nullable=False),
            sa.Column("endpoint", sa.String(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("auth_config_json", sa.JSON(), nullable=True),
            sa.Column("capabilities_json", sa.JSON(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("updated_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_mcp_servers_tenant_workspace_enabled", "mcp_servers", ["tenant_id", "workspace_id", "enabled"])
        op.create_index("ix_mcp_servers_tenant_workspace_name", "mcp_servers", ["tenant_id", "workspace_id", "name"])

    if "approval_requests" not in tables:
        op.create_table(
            "approval_requests",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("run_id", sa.String(), nullable=True),
            sa.Column("task_id", sa.String(), nullable=True),
            sa.Column("thread_id", sa.String(), nullable=True),
            sa.Column("agent_id", sa.String(), nullable=True),
            sa.Column("title", sa.String(), nullable=False),
            sa.Column("policy_ref", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("details_json", sa.JSON(), nullable=True),
            sa.Column("requested_by", sa.String(), nullable=True),
            sa.Column("resolved_by", sa.String(), nullable=True),
            sa.Column("resolution_note", sa.Text(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_approval_requests_scope_status",
            "approval_requests",
            ["tenant_id", "workspace_id", "status"],
        )
        op.create_index("ix_approval_requests_run_task", "approval_requests", ["run_id", "task_id"])

    if "run_feedbacks" not in tables:
        op.create_table(
            "run_feedbacks",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("run_id", sa.String(), nullable=True),
            sa.Column("task_id", sa.String(), nullable=True),
            sa.Column("thread_id", sa.String(), nullable=True),
            sa.Column("agent_id", sa.String(), nullable=True),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_run_feedbacks_scope_created",
            "run_feedbacks",
            ["tenant_id", "workspace_id", "created_at"],
        )
        op.create_index("ix_run_feedbacks_run_agent", "run_feedbacks", ["run_id", "agent_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "run_feedbacks" in tables:
        op.drop_index("ix_run_feedbacks_run_agent", table_name="run_feedbacks")
        op.drop_index("ix_run_feedbacks_scope_created", table_name="run_feedbacks")
        op.drop_table("run_feedbacks")

    if "approval_requests" in tables:
        op.drop_index("ix_approval_requests_run_task", table_name="approval_requests")
        op.drop_index("ix_approval_requests_scope_status", table_name="approval_requests")
        op.drop_table("approval_requests")

    if "mcp_servers" in tables:
        op.drop_index("ix_mcp_servers_tenant_workspace_name", table_name="mcp_servers")
        op.drop_index("ix_mcp_servers_tenant_workspace_enabled", table_name="mcp_servers")
        op.drop_table("mcp_servers")

    if "skill_publishes" in tables:
        op.drop_index("ix_skill_publishes_version_id", table_name="skill_publishes")
        op.drop_index("ix_skill_publishes_skill_id", table_name="skill_publishes")
        op.drop_table("skill_publishes")

    if "skill_versions" in tables:
        op.drop_index("ix_skill_versions_skill_id_status", table_name="skill_versions")
        op.drop_table("skill_versions")

    if "skills" in tables:
        op.drop_index("ix_skills_tenant_workspace_name", table_name="skills")
        op.drop_index("ix_skills_tenant_workspace_status", table_name="skills")
        op.drop_table("skills")
