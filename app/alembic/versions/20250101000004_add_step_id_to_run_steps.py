"""add_step_id_to_run_steps

Revision ID: 20250101000004
Revises: 20250101000003
Create Date: 2025-01-01 00:00:04.000000

Add step_id field to run_steps table.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250101000004'
down_revision = '20250101000003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add step_id column to run_steps table
    op.add_column('run_steps', sa.Column('step_id', sa.String(), nullable=True))
    op.create_index(
        'ix_run_steps_step_id', 'run_steps', ['step_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_run_steps_step_id', table_name='run_steps')
    op.drop_column('run_steps', 'step_id')

