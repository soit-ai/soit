"""workflow_tables

Revision ID: 20250101000001
Revises: 20250101000000
Create Date: 2025-01-01 00:00:01.000000

Create workflow tables (workflows and workflow_versions).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250101000001'
down_revision = '20250101000000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create workflows table
    op.create_table(
        'workflows',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('current_version_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workflows_tenant_id', 'workflows', ['tenant_id'], unique=False)
    op.create_index('ix_workflows_workspace_id', 'workflows', ['workspace_id'], unique=False)
    op.create_unique_constraint(
        'uq_workflows_tenant_workspace_name',
        'workflows',
        ['tenant_id', 'workspace_id', 'name']
    )
    
    # Create workflow_versions table
    op.create_table(
        'workflow_versions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('workflow_id', sa.String(), nullable=False),
        sa.Column('graph_json', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workflow_versions_tenant_id', 'workflow_versions', ['tenant_id'], unique=False)
    op.create_index('ix_workflow_versions_workspace_id', 'workflow_versions', ['workspace_id'], unique=False)
    op.create_index('ix_workflow_versions_workflow_id', 'workflow_versions', ['workflow_id'], unique=False)
    op.create_index(
        'ix_workflow_versions_tenant_workspace_workflow_created',
        'workflow_versions',
        ['tenant_id', 'workspace_id', 'workflow_id', sa.text('created_at DESC')],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_workflow_versions_tenant_workspace_workflow_created', table_name='workflow_versions')
    op.drop_index('ix_workflow_versions_workflow_id', table_name='workflow_versions')
    op.drop_index('ix_workflow_versions_workspace_id', table_name='workflow_versions')
    op.drop_index('ix_workflow_versions_tenant_id', table_name='workflow_versions')
    op.drop_table('workflow_versions')
    
    op.drop_constraint('uq_workflows_tenant_workspace_name', 'workflows', type_='unique')
    op.drop_index('ix_workflows_workspace_id', table_name='workflows')
    op.drop_index('ix_workflows_tenant_id', table_name='workflows')
    op.drop_table('workflows')

