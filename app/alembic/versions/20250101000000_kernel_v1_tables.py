"""kernel_v1_tables

Revision ID: 20250101000000
Revises: 
Create Date: 2025-01-01 00:00:00.000000

Create kernel v1 core tables (runs, run_steps, run_artifacts, run_costs).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250101000000'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create runs table
    op.create_table(
        'runs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('mode', sa.String(), nullable=False),
        sa.Column('app_version_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('input_summary', sa.Text(), nullable=True),
        sa.Column('output_summary', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_runs_tenant_id', 'runs', ['tenant_id'], unique=False
    )
    op.create_index(
        'ix_runs_workspace_id', 'runs', ['workspace_id'], unique=False
    )
    op.create_index(
        'ix_runs_tenant_workspace_started', 'runs',
        ['tenant_id', 'workspace_id', sa.text('started_at DESC')],
        unique=False
    )
    
    # Create run_steps table
    op.create_table(
        'run_steps',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('step_type', sa.String(), nullable=False),
        sa.Column('node_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('input_summary', sa.Text(), nullable=True),
        sa.Column('output_summary', sa.Text(), nullable=True),
        sa.Column('metrics_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_code', sa.String(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_run_steps_tenant_id', 'run_steps', ['tenant_id'], unique=False
    )
    op.create_index(
        'ix_run_steps_workspace_id', 'run_steps', ['workspace_id'], unique=False
    )
    op.create_index(
        'ix_run_steps_run_id', 'run_steps', ['run_id'], unique=False
    )
    op.create_index(
        'ix_run_steps_tenant_workspace_run', 'run_steps',
        ['tenant_id', 'workspace_id', 'run_id'],
        unique=False
    )
    
    # Create run_artifacts table
    op.create_table(
        'run_artifacts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('storage_key', sa.String(), nullable=False),
        sa.Column('meta_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_run_artifacts_tenant_id', 'run_artifacts', ['tenant_id'], unique=False
    )
    op.create_index(
        'ix_run_artifacts_workspace_id', 'run_artifacts', ['workspace_id'], unique=False
    )
    op.create_index(
        'ix_run_artifacts_run_id', 'run_artifacts', ['run_id'], unique=False
    )
    op.create_index(
        'ix_run_artifacts_tenant_workspace_run', 'run_artifacts',
        ['tenant_id', 'workspace_id', 'run_id'],
        unique=False
    )
    
    # Create run_costs table
    op.create_table(
        'run_costs',
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('tokens_prompt', sa.Integer(), nullable=False),
        sa.Column('tokens_completion', sa.Integer(), nullable=False),
        sa.Column('embedding_count', sa.Integer(), nullable=False),
        sa.Column('rerank_count', sa.Integer(), nullable=False),
        sa.Column('ms_total', sa.Integer(), nullable=False),
        sa.Column('storage_bytes', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ),
        sa.PrimaryKeyConstraint('run_id')
    )
    op.create_index(
        'ix_run_costs_tenant_id', 'run_costs', ['tenant_id'], unique=False
    )
    op.create_index(
        'ix_run_costs_workspace_id', 'run_costs', ['workspace_id'], unique=False
    )
    op.create_index(
        'ix_run_costs_tenant_workspace_run', 'run_costs',
        ['tenant_id', 'workspace_id', 'run_id'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_run_costs_tenant_workspace_run', table_name='run_costs')
    op.drop_index('ix_run_costs_workspace_id', table_name='run_costs')
    op.drop_index('ix_run_costs_tenant_id', table_name='run_costs')
    op.drop_table('run_costs')
    
    op.drop_index('ix_run_artifacts_tenant_workspace_run', table_name='run_artifacts')
    op.drop_index('ix_run_artifacts_run_id', table_name='run_artifacts')
    op.drop_index('ix_run_artifacts_workspace_id', table_name='run_artifacts')
    op.drop_index('ix_run_artifacts_tenant_id', table_name='run_artifacts')
    op.drop_table('run_artifacts')
    
    op.drop_index('ix_run_steps_tenant_workspace_run', table_name='run_steps')
    op.drop_index('ix_run_steps_run_id', table_name='run_steps')
    op.drop_index('ix_run_steps_workspace_id', table_name='run_steps')
    op.drop_index('ix_run_steps_tenant_id', table_name='run_steps')
    op.drop_table('run_steps')
    
    op.drop_index('ix_runs_tenant_workspace_started', table_name='runs')
    op.drop_index('ix_runs_workspace_id', table_name='runs')
    op.drop_index('ix_runs_tenant_id', table_name='runs')
    op.drop_table('runs')

