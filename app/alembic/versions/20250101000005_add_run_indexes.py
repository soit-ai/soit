"""add_run_indexes

Revision ID: 20250101000005
Revises: 20250101000004
Create Date: 2025-01-01 00:00:05.000000

Add indexes for workflow run queries.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250101000005'
down_revision = '20250101000004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add composite index for workflow run queries
    # Supports queries filtering by tenant_id, workspace_id, app_version_id (workflow_id), mode, and ordering by created_at
    op.create_index(
        'ix_runs_tenant_workspace_app_version_mode_created',
        'runs',
        ['tenant_id', 'workspace_id', 'app_version_id', 'mode', sa.text('created_at DESC')],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_runs_tenant_workspace_app_version_mode_created', table_name='runs')

