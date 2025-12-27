"""chat_tables

Revision ID: 20250101000003
Revises: 20250101000002
Create Date: 2025-01-01 00:00:03.000000

Create chat tables (conversations and messages).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250101000003'
down_revision = '20250101000002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create conversations table
    op.create_table(
        'conversations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=True),
        sa.Column('metadata_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_conversations_tenant_id', 'conversations', ['tenant_id'], unique=False
    )
    op.create_index(
        'ix_conversations_workspace_id', 'conversations', ['workspace_id'], unique=False
    )
    op.create_index(
        'ix_conversations_tenant_workspace_updated', 'conversations',
        ['tenant_id', 'workspace_id', sa.text('updated_at DESC')],
        unique=False
    )
    op.create_index(
        'ix_conversations_deleted_at', 'conversations', ['deleted_at'], unique=False
    )
    
    # Create messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('tenant_id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        'ix_messages_tenant_id', 'messages', ['tenant_id'], unique=False
    )
    op.create_index(
        'ix_messages_workspace_id', 'messages', ['workspace_id'], unique=False
    )
    op.create_index(
        'ix_messages_conversation_id', 'messages', ['conversation_id'], unique=False
    )
    op.create_index(
        'ix_messages_tenant_workspace_conversation_created', 'messages',
        ['tenant_id', 'workspace_id', 'conversation_id', sa.text('created_at')],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_messages_tenant_workspace_conversation_created', table_name='messages')
    op.drop_index('ix_messages_conversation_id', table_name='messages')
    op.drop_index('ix_messages_workspace_id', table_name='messages')
    op.drop_index('ix_messages_tenant_id', table_name='messages')
    op.drop_table('messages')
    
    op.drop_index('ix_conversations_deleted_at', table_name='conversations')
    op.drop_index('ix_conversations_tenant_workspace_updated', table_name='conversations')
    op.drop_index('ix_conversations_workspace_id', table_name='conversations')
    op.drop_index('ix_conversations_tenant_id', table_name='conversations')
    op.drop_table('conversations')

