-- Dataset module DDL (PostgreSQL 15+)
-- NOTE: This file is a reference for Alembic migrations.
-- All IDs are stored as TEXT for ULID/UUID flexibility.

CREATE TABLE IF NOT EXISTS dataset (
  id              TEXT PRIMARY KEY,
  tenant_id        TEXT NOT NULL,
  workspace_id     TEXT NOT NULL,
  name             TEXT NOT NULL,
  type             TEXT NOT NULL,
  description      TEXT,
  status           TEXT NOT NULL DEFAULT 'active',
  visibility       TEXT NOT NULL DEFAULT 'private',

  settings_json    JSONB NOT NULL DEFAULT '{}'::jsonb,
  chunking_json    JSONB NOT NULL DEFAULT '{}'::jsonb,
  retrieval_json   JSONB NOT NULL DEFAULT '{}'::jsonb,

  default_embedding_model_ref TEXT,
  default_reranker_ref        TEXT,
  default_index_id            TEXT,

  doc_count       BIGINT NOT NULL DEFAULT 0,
  chunk_count     BIGINT NOT NULL DEFAULT 0,
  last_ingested_at TIMESTAMPTZ,
  last_indexed_at  TIMESTAMPTZ,

  tags            JSONB NOT NULL DEFAULT '[]'::jsonb,

  created_by      TEXT,
  updated_by      TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at      TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_dataset_name
  ON dataset (tenant_id, workspace_id, name)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_dataset_scope_status
  ON dataset (tenant_id, workspace_id, status);

CREATE INDEX IF NOT EXISTS ix_dataset_scope_updated
  ON dataset (tenant_id, workspace_id, updated_at DESC);


CREATE TABLE IF NOT EXISTS dataset_documents (
  id              TEXT PRIMARY KEY,
  tenant_id        TEXT NOT NULL,
  workspace_id     TEXT NOT NULL,
  dataset_id       TEXT NOT NULL REFERENCES dataset(id),

  doc_key          TEXT NOT NULL,
  version          INT  NOT NULL,
  is_latest        BOOLEAN NOT NULL DEFAULT TRUE,

  source_type      TEXT NOT NULL,
  source_uri       TEXT,
  external_id      TEXT,
  file_id          TEXT,

  title            TEXT,
  language         TEXT,
  mime_type        TEXT,
  filename         TEXT,
  size_bytes       BIGINT,
  checksum         TEXT,
  content_hash     TEXT,

  status           TEXT NOT NULL DEFAULT 'uploaded',
  error_code       TEXT,
  error_message    TEXT,
  retry_count      INT NOT NULL DEFAULT 0,

  raw_text_artifact_key TEXT,
  parsed_artifact_key   TEXT,

  chunking_json     JSONB,
  parse_meta_json   JSONB NOT NULL DEFAULT '{}'::jsonb,
  index_meta_json   JSONB NOT NULL DEFAULT '{}'::jsonb,

  access_policy_json JSONB NOT NULL DEFAULT '{}'::jsonb,

  created_by      TEXT,
  updated_by      TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at      TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_dataset_doc_version
  ON dataset_documents (tenant_id, workspace_id, dataset_id, doc_key, version)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_dataset_docs_latest
  ON dataset_documents (tenant_id, workspace_id, dataset_id, is_latest)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_dataset_docs_status
  ON dataset_documents (tenant_id, workspace_id, dataset_id, status)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_dataset_docs_updated
  ON dataset_documents (tenant_id, workspace_id, dataset_id, updated_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_dataset_docs_content_hash
  ON dataset_documents (tenant_id, workspace_id, dataset_id, content_hash)
  WHERE deleted_at IS NULL AND content_hash IS NOT NULL;


CREATE TABLE IF NOT EXISTS dataset_chunks (
  id              TEXT PRIMARY KEY,
  tenant_id        TEXT NOT NULL,
  workspace_id     TEXT NOT NULL,

  dataset_id       TEXT NOT NULL REFERENCES dataset(id),
  document_id      TEXT NOT NULL REFERENCES dataset_documents(id),
  document_version INT  NOT NULL,

  chunk_no         INT  NOT NULL,
  chunk_key        TEXT,
  content_hash     TEXT,

  text_preview     TEXT,
  text_artifact_key TEXT,

  start_offset     INT,
  end_offset       INT,
  page_no          INT,
  section_path     JSONB NOT NULL DEFAULT '[]'::jsonb,
  bbox_json        JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_meta_json JSONB NOT NULL DEFAULT '{}'::jsonb,

  char_count       INT,
  token_count      INT,

  embedding_model_ref TEXT,
  vector_ref          TEXT,
  indexed_at          TIMESTAMPTZ,
  index_status        TEXT NOT NULL DEFAULT 'pending',
  index_error         TEXT,

  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_dataset_chunk_no
  ON dataset_chunks (tenant_id, workspace_id, document_id, chunk_no, document_version);

CREATE INDEX IF NOT EXISTS ix_dataset_chunks_doc
  ON dataset_chunks (tenant_id, workspace_id, dataset_id, document_id);

CREATE INDEX IF NOT EXISTS ix_dataset_chunks_status
  ON dataset_chunks (tenant_id, workspace_id, dataset_id, index_status);

CREATE INDEX IF NOT EXISTS ix_dataset_chunks_updated
  ON dataset_chunks (tenant_id, workspace_id, dataset_id, updated_at DESC);


CREATE TABLE IF NOT EXISTS dataset_indexs (
  id              TEXT PRIMARY KEY,
  tenant_id        TEXT NOT NULL,
  workspace_id     TEXT NOT NULL,
  dataset_id       TEXT NOT NULL REFERENCES dataset(id),

  name             TEXT NOT NULL,
  is_primary       BOOLEAN NOT NULL DEFAULT FALSE,

  provider         TEXT NOT NULL,
  endpoint_ref     TEXT,
  collection_name  TEXT,
  partition_strategy TEXT,
  namespace        TEXT,

  embedding_model_ref TEXT NOT NULL,
  dimension        INT  NOT NULL,
  metric_type      TEXT NOT NULL,

  index_params_json  JSONB NOT NULL DEFAULT '{}'::jsonb,
  search_params_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  reranker_ref       TEXT,
  filters_json       JSONB NOT NULL DEFAULT '{}'::jsonb,

  status           TEXT NOT NULL DEFAULT 'draft',
  build_version    INT  NOT NULL DEFAULT 1,
  last_build_at    TIMESTAMPTZ,

  doc_count        BIGINT NOT NULL DEFAULT 0,
  chunk_count      BIGINT NOT NULL DEFAULT 0,
  vector_count     BIGINT NOT NULL DEFAULT 0,

  last_error_code   TEXT,
  last_error_message TEXT,

  created_by      TEXT,
  updated_by      TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  deleted_at      TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_dataset_index_name
  ON dataset_indexs (tenant_id, workspace_id, dataset_id, name)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_dataset_index_status
  ON dataset_indexs (tenant_id, workspace_id, dataset_id, status)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_dataset_index_primary
  ON dataset_indexs (tenant_id, workspace_id, dataset_id, is_primary)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_dataset_index_updated
  ON dataset_indexs (tenant_id, workspace_id, updated_at DESC)
  WHERE deleted_at IS NULL;
