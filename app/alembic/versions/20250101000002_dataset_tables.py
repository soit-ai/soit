"""dataset_tables

Revision ID: 20250101000002
Revises: 20250101000001
Create Date: 2025-01-01 00:00:02.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '20250101000002'
down_revision = '20250101000001'
branch_labels = None
depends_on = None


def upgrade():
    # Create dataset table
    op.create_table(
        'dataset',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('tenant_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('workspace_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('visibility', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('settings_json', sa.JSON(), nullable=False),
        sa.Column('chunking_json', sa.JSON(), nullable=False),
        sa.Column('retrieval_json', sa.JSON(), nullable=False),
        sa.Column('default_embedding_model_ref', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('default_reranker_ref', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('default_index_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('doc_count', sa.Integer(), nullable=False),
        sa.Column('chunk_count', sa.Integer(), nullable=False),
        sa.Column('last_ingested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_indexed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_by', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('updated_by', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'workspace_id', 'name', name='uq_dataset_tenant_workspace_name')
    )
    op.create_index(op.f('ix_dataset_tenant_id'), 'dataset', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_dataset_workspace_id'), 'dataset', ['workspace_id'], unique=False)
    
    # Create dataset_documents table
    op.create_table(
        'dataset_documents',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('tenant_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('workspace_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('dataset_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('doc_key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('is_latest', sa.Boolean(), nullable=False),
        sa.Column('source_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('source_uri', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('external_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('file_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('language', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('mime_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('filename', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('checksum', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('content_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('error_code', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('raw_text_artifact_key', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('parsed_artifact_key', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('chunking_json', sa.JSON(), nullable=True),
        sa.Column('parse_meta_json', sa.JSON(), nullable=False),
        sa.Column('index_meta_json', sa.JSON(), nullable=False),
        sa.Column('access_policy_json', sa.JSON(), nullable=False),
        sa.Column('created_by', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('updated_by', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['dataset_id'], ['dataset.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'workspace_id', 'dataset_id', 'doc_key', 'version', name='uq_document_tenant_workspace_dataset_key_version')
    )
    op.create_index(op.f('ix_dataset_documents_tenant_id'), 'dataset_documents', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_dataset_documents_workspace_id'), 'dataset_documents', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_dataset_documents_dataset_id'), 'dataset_documents', ['dataset_id'], unique=False)
    op.create_index('ix_dataset_documents_dataset_latest', 'dataset_documents', ['tenant_id', 'workspace_id', 'dataset_id', 'is_latest'], unique=False)
    
    # Create dataset_chunks table
    op.create_table(
        'dataset_chunks',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('tenant_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('workspace_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('dataset_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('document_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('document_version', sa.Integer(), nullable=False),
        sa.Column('chunk_no', sa.Integer(), nullable=False),
        sa.Column('chunk_key', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('content_hash', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('text_preview', sqlmodel.sql.sqltypes.AutoString(length=2048), nullable=True),
        sa.Column('text_artifact_key', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('start_offset', sa.Integer(), nullable=True),
        sa.Column('end_offset', sa.Integer(), nullable=True),
        sa.Column('page_no', sa.Integer(), nullable=True),
        sa.Column('section_path', sa.JSON(), nullable=False),
        sa.Column('bbox_json', sa.JSON(), nullable=False),
        sa.Column('source_meta_json', sa.JSON(), nullable=False),
        sa.Column('char_count', sa.Integer(), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('embedding_model_ref', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('vector_ref', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('index_status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('index_error', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['dataset_documents.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'workspace_id', 'document_id', 'chunk_no', 'document_version', name='uq_chunk_tenant_workspace_document_chunk_version')
    )
    op.create_index(op.f('ix_dataset_chunks_tenant_id'), 'dataset_chunks', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_dataset_chunks_workspace_id'), 'dataset_chunks', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_dataset_chunks_dataset_id'), 'dataset_chunks', ['dataset_id'], unique=False)
    op.create_index(op.f('ix_dataset_chunks_document_id'), 'dataset_chunks', ['document_id'], unique=False)
    
    # Create dataset_indexs table
    op.create_table(
        'dataset_indexs',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('tenant_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('workspace_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('dataset_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False),
        sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('endpoint_ref', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('collection_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('partition_strategy', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('namespace', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('embedding_model_ref', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('dimension', sa.Integer(), nullable=False),
        sa.Column('metric_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('index_params_json', sa.JSON(), nullable=False),
        sa.Column('search_params_json', sa.JSON(), nullable=False),
        sa.Column('reranker_ref', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('filters_json', sa.JSON(), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('build_version', sa.Integer(), nullable=False),
        sa.Column('last_build_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('doc_count', sa.Integer(), nullable=False),
        sa.Column('chunk_count', sa.Integer(), nullable=False),
        sa.Column('vector_count', sa.Integer(), nullable=False),
        sa.Column('last_error_code', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('last_error_message', sa.Text(), nullable=True),
        sa.Column('created_by', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('updated_by', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['dataset_id'], ['dataset.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'workspace_id', 'dataset_id', 'name', name='uq_index_tenant_workspace_dataset_name')
    )
    op.create_index(op.f('ix_dataset_indexs_tenant_id'), 'dataset_indexs', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_dataset_indexs_workspace_id'), 'dataset_indexs', ['workspace_id'], unique=False)
    op.create_index(op.f('ix_dataset_indexs_dataset_id'), 'dataset_indexs', ['dataset_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_dataset_indexs_dataset_id'), table_name='dataset_indexs')
    op.drop_index(op.f('ix_dataset_indexs_workspace_id'), table_name='dataset_indexs')
    op.drop_index(op.f('ix_dataset_indexs_tenant_id'), table_name='dataset_indexs')
    op.drop_table('dataset_indexs')
    
    op.drop_index(op.f('ix_dataset_chunks_document_id'), table_name='dataset_chunks')
    op.drop_index(op.f('ix_dataset_chunks_dataset_id'), table_name='dataset_chunks')
    op.drop_index(op.f('ix_dataset_chunks_workspace_id'), table_name='dataset_chunks')
    op.drop_index(op.f('ix_dataset_chunks_tenant_id'), table_name='dataset_chunks')
    op.drop_table('dataset_chunks')
    
    op.drop_index('ix_dataset_documents_dataset_latest', table_name='dataset_documents')
    op.drop_index(op.f('ix_dataset_documents_dataset_id'), table_name='dataset_documents')
    op.drop_index(op.f('ix_dataset_documents_workspace_id'), table_name='dataset_documents')
    op.drop_index(op.f('ix_dataset_documents_tenant_id'), table_name='dataset_documents')
    op.drop_table('dataset_documents')
    
    op.drop_index(op.f('ix_dataset_workspace_id'), table_name='dataset')
    op.drop_index(op.f('ix_dataset_tenant_id'), table_name='dataset')
    op.drop_table('dataset')

