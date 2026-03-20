"""add standalone agent core tables

Revision ID: 20260306100000_agent_core_tables
Revises: 20260211170000_message_parent_id
Create Date: 2026-03-06 10:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260306100000_agent_core_tables"
down_revision = "20260211170000_message_parent_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "agents" not in tables:
        op.create_table(
            "agents",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("visibility", sa.String(), nullable=False),
            sa.Column("tags", sa.JSON(), nullable=True),
            sa.Column("profile_json", sa.JSON(), nullable=True),
            sa.Column("instructions_json", sa.JSON(), nullable=True),
            sa.Column("execution_policy_json", sa.JSON(), nullable=True),
            sa.Column("runtime_config_json", sa.JSON(), nullable=True),
            sa.Column("default_model_ref", sa.String(), nullable=True),
            sa.Column("current_version_id", sa.String(), nullable=True),
            sa.Column("published_version_id", sa.String(), nullable=True),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("updated_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_agents_tenant_workspace_status", "agents", ["tenant_id", "workspace_id", "status"])
        op.create_index("ix_agents_tenant_workspace_name", "agents", ["tenant_id", "workspace_id", "name"])

    if "agent_versions" not in tables:
        op.create_table(
            "agent_versions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("agent_id", sa.String(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("spec_schema", sa.String(), nullable=False),
            sa.Column("spec_json", sa.JSON(), nullable=False),
            sa.Column("checksum", sa.String(), nullable=True),
            sa.Column("created_from_version_id", sa.String(), nullable=True),
            sa.Column("changelog", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
            sa.UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_id_version"),
        )
        op.create_index("ix_agent_versions_agent_id_status", "agent_versions", ["agent_id", "status"])
        op.create_index("ix_agent_versions_checksum", "agent_versions", ["checksum"])

    if "agent_bindings" not in tables:
        op.create_table(
            "agent_bindings",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("agent_id", sa.String(), nullable=False),
            sa.Column("agent_version_id", sa.String(), nullable=True),
            sa.Column("binding_type", sa.String(), nullable=False),
            sa.Column("target_id", sa.String(), nullable=True),
            sa.Column("target_key", sa.String(), nullable=True),
            sa.Column("config_json", sa.JSON(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
            sa.ForeignKeyConstraint(["agent_version_id"], ["agent_versions.id"]),
            sa.UniqueConstraint(
                "agent_version_id",
                "binding_type",
                "target_id",
                "target_key",
                name="uq_agent_bindings_version_target",
            ),
        )
        op.create_index("ix_agent_bindings_agent_id", "agent_bindings", ["agent_id"])
        op.create_index("ix_agent_bindings_agent_version_id", "agent_bindings", ["agent_version_id"])
        op.create_index("ix_agent_bindings_binding_type", "agent_bindings", ["binding_type"])

    if "agent_publishes" not in tables:
        op.create_table(
            "agent_publishes",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), nullable=False),
            sa.Column("workspace_id", sa.String(), nullable=False),
            sa.Column("agent_id", sa.String(), nullable=False),
            sa.Column("agent_version_id", sa.String(), nullable=False),
            sa.Column("scope", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("rollback_of_publish_id", sa.String(), nullable=True),
            sa.Column("created_by", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
            sa.ForeignKeyConstraint(["agent_version_id"], ["agent_versions.id"]),
        )
        op.create_index("ix_agent_publishes_agent_id", "agent_publishes", ["agent_id"])
        op.create_index("ix_agent_publishes_version_id", "agent_publishes", ["agent_version_id"])
        op.create_index("ix_agent_publishes_scope_status", "agent_publishes", ["scope", "status"])


def downgrade() -> None:
    op.drop_index("ix_agent_publishes_scope_status", table_name="agent_publishes")
    op.drop_index("ix_agent_publishes_version_id", table_name="agent_publishes")
    op.drop_index("ix_agent_publishes_agent_id", table_name="agent_publishes")
    op.drop_table("agent_publishes")

    op.drop_index("ix_agent_bindings_binding_type", table_name="agent_bindings")
    op.drop_index("ix_agent_bindings_agent_version_id", table_name="agent_bindings")
    op.drop_index("ix_agent_bindings_agent_id", table_name="agent_bindings")
    op.drop_table("agent_bindings")

    op.drop_index("ix_agent_versions_checksum", table_name="agent_versions")
    op.drop_index("ix_agent_versions_agent_id_status", table_name="agent_versions")
    op.drop_table("agent_versions")

    op.drop_index("ix_agents_tenant_workspace_name", table_name="agents")
    op.drop_index("ix_agents_tenant_workspace_status", table_name="agents")
    op.drop_table("agents")
