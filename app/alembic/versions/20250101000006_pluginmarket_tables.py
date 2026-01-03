"""pluginmarket_tables

Revision ID: 20250101000006
Revises: 20250101000005
Create Date: 2025-01-01 00:00:06.000000

Create pluginmarket tables (plugins and plugin_installations).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20250101000006'
down_revision = '20250101000005'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'plugins',
        sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('workspace_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('version', sa.String(length=64), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('spec_json', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('manifest_json', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('metadata_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('published', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('installed_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_by', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_plugins_tenant_id', 'plugins', ['tenant_id'])
    op.create_index('ix_plugins_workspace_id', 'plugins', ['workspace_id'])
    op.create_index('ix_plugins_name', 'plugins', ['name'])
    op.create_index('ix_plugins_version', 'plugins', ['version'])
    op.create_index('ix_plugins_published', 'plugins', ['published'])

    op.create_table(
        'plugin_installations',
        sa.Column('id', sa.String(length=64), primary_key=True, nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('workspace_id', sa.String(length=64), nullable=False),
        sa.Column('plugin_id', sa.String(length=64), sa.ForeignKey('plugins.id'), nullable=False),
        sa.Column('installed_by', sa.String(length=64), nullable=True),
        sa.Column('config_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_plugin_installations_tenant_id', 'plugin_installations', ['tenant_id'])
    op.create_index('ix_plugin_installations_workspace_id', 'plugin_installations', ['workspace_id'])
    op.create_index('ix_plugin_installations_plugin_id', 'plugin_installations', ['plugin_id'])


def downgrade():
    op.drop_index('ix_plugin_installations_plugin_id', table_name='plugin_installations')
    op.drop_index('ix_plugin_installations_workspace_id', table_name='plugin_installations')
    op.drop_index('ix_plugin_installations_tenant_id', table_name='plugin_installations')
    op.drop_table('plugin_installations')

    op.drop_index('ix_plugins_published', table_name='plugins')
    op.drop_index('ix_plugins_version', table_name='plugins')
    op.drop_index('ix_plugins_name', table_name='plugins')
    op.drop_index('ix_plugins_workspace_id', table_name='plugins')
    op.drop_index('ix_plugins_tenant_id', table_name='plugins')
    op.drop_table('plugins')
