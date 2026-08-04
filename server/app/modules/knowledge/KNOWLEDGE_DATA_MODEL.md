# Knowledge Data Module (internal storage model, long-term stable v1)

> This document describes the internal storage model behind the current
> knowledge-base capability. The external product language, database table
> names, and code directories are all unified as `knowledge`.

This file defines the **long-term stable data model** for SOIT knowledge
bases. Its goals are:

- Enforce two-level `tenant_id + workspace_id` isolation
- Support multiple document sources (upload / crawler / API)
- Support multi-version documents and incremental rebuilds
- Support multiple indexes (different embeddings / providers / retrieval
  strategies)
- The database stores **summaries and metadata only**; large text and parsing
  artifacts go to object storage; vectors go to the vector store
- Reserve fields for audit / observability / billing to minimize future
  schema changes

> Table names as required: `knowledge`, `knowledge_documents`,
> `knowledge_chunks`, `knowledge_indexes`

---

## 0. Shared Conventions

### 0.1 Primary keys and timestamps
- `id`: ULID recommended (string or 128-bit), sortable by time
- `created_at`, `updated_at`: `timestamptz`
- `deleted_at`: soft delete (optional, recommended)
- `created_by`, `updated_by`: `user_id` (nullable; empty for system tasks)

### 0.2 Isolation fields (mandatory)
- Except for a very small number of tenant-level global tables, every
  business table includes:
  - `tenant_id` (NOT NULL)
  - `workspace_id` (NOT NULL)

### 0.3 JSON field policy
- `*_json` fields hold **evolvable configuration/metadata only**, to avoid
  frequent column additions
- Fields used in critical queries must be dedicated columns (e.g. status /
  type / version)

### 0.4 State machines (recommended enums)
- Document pipeline: `uploaded -> parsed -> chunked -> indexed`
  (failure: `failed`)
- Index pipeline: `draft -> building -> ready`
  (failure: `failed`; deactivated: `disabled`)

---

## 1. knowledge (knowledge base)

### 1.1 Design notes
- Knowledge-base names are unique within a workspace
- A knowledge base holds default chunk/retrieval strategies, which an index
  may override
- Supports logical deletion, tags, description, and statistics (for display /
  billing / quota)

### 1.2 Fields (recommended)
- Base
  - `id` PK
  - `tenant_id`, `workspace_id` (NOT NULL)
  - `name` (NOT NULL)
  - `type` (NOT NULL), e.g. `document | qa | code | graph`
  - `description` (NULL)
  - `status` (NOT NULL), e.g. `active | archived | disabled`
  - `visibility` (NOT NULL), e.g. `private | workspace | tenant`
- Configuration (evolvable)
  - `settings_json`: general knowledge-base configuration (parser / language /
    filter rules, etc.)
  - `chunking_json`: default chunking strategy (size/overlap/separators)
  - `retrieval_json`: default retrieval strategy (top_k/rerank/filters)
- Bindings and defaults
  - `default_embedding_model_ref`: e.g. `model:openai:text-embedding-3-large`
  - `default_reranker_ref` (nullable)
  - `default_index_id` (nullable, points to knowledge_indexes.id)
- Statistics (denormalized for list views)
  - `doc_count` (NOT NULL default 0)
  - `chunk_count` (NOT NULL default 0)
  - `last_ingested_at` (NULL)
  - `last_indexed_at` (NULL)
- Audit
  - `tags` (text[] or json)
  - `created_by`, `updated_by`, `created_at`, `updated_at`, `deleted_at`

### 1.3 Key constraints and indexes
- UNIQUE: `(tenant_id, workspace_id, name)`
- INDEX:
  - `(tenant_id, workspace_id, status)`
  - `(tenant_id, workspace_id, updated_at DESC)`

---

## 2. knowledge_documents

### 2.1 Design notes
- Documents within a knowledge base support **multiple versions** (`version`)
- Multiple sources: file upload, crawled URL, API push, manual text
- Parsing artifacts (extracted text, structured output) belong in object
  storage; the database stores references and summaries
- Reserved for future permissions and compliance: `access_policy_json`

### 2.2 Fields (recommended)
- Identity and isolation
  - `id` PK
  - `tenant_id`, `workspace_id` (NOT NULL)
  - `knowledge_id` (FK -> knowledge.id)
  - `doc_key`: stable key for the same logical document (e.g. based on URL or
    a business id), used to aggregate versions (NOT NULL)
  - `version`: incrementing from 1 (NOT NULL)
  - `is_latest`: latest-version marker (NOT NULL default true)
- Source
  - `source_kind`: `upload | crawler | api | manual` (NOT NULL)
  - `source_uri`: URL / external reference (nullable)
  - `external_id`: id in the source business system (nullable)
  - `file_id`: uploaded file id (nullable, points to the files module)
- File/content metadata
  - `title` (nullable)
  - `language` (nullable, ISO 639-1)
  - `mime_type` (nullable)
  - `filename` (nullable)
  - `size_bytes` (nullable)
  - `checksum` (nullable, sha256)
  - `content_hash` (nullable, hash of the source text, for deduplication)
- Pipeline status
  - `status`: `uploaded | parsing | parsed | chunking | chunked | indexing |
    indexed | failed | deleted`
  - `error_code` (nullable)
  - `error_message` (nullable, short text recommended)
  - `retry_count` (NOT NULL default 0)
- Parsing/chunking/indexing metadata (object-storage references)
  - `raw_text_artifact_key`: extracted plain text (nullable)
  - `parsed_artifact_key`: structured parsing output (nullable, e.g.
    markdown/json)
  - `chunking_json`: chunking strategy used by this version (nullable,
    defaults to knowledge.chunking_json)
  - `parse_meta_json`: page count, table count, image count, duration, etc.
  - `index_meta_json`: vectors written, failure summary, etc.
- Permissions and compliance
  - `access_policy_json`: e.g. department/role visibility, redaction policy
    (nullable)
- Audit
  - `created_by`, `updated_by`, `created_at`, `updated_at`, `deleted_at`

### 2.3 Key constraints and indexes
- UNIQUE:
  - `(tenant_id, workspace_id, knowledge_id, doc_key, version)`
- Recommended indexes:
  - `(tenant_id, workspace_id, knowledge_id, is_latest)`
  - `(tenant_id, workspace_id, knowledge_id, status)`
  - `(tenant_id, workspace_id, knowledge_id, updated_at DESC)`
  - `(tenant_id, workspace_id, knowledge_id, content_hash)` (optional, for
    deduplication)

> Guarantee `is_latest` transactionally: only one row with latest=true per
> `(knowledge_id, doc_key)`.

---

## 3. knowledge_chunks

### 3.1 Design notes
- A chunk does not necessarily store full text: prefer `text_artifact_key`
  pointing to object storage, with the database holding a summary and
  location info
- Supports source location: page number / paragraph / code block / heading
  hierarchy
- Supports vector-store mapping: each chunk has a `vector_ref` (or the
  primary key produced by upsert)

### 3.2 Fields (recommended)
- Identity and isolation
  - `id` PK
  - `tenant_id`, `workspace_id` (NOT NULL)
  - `knowledge_id` (denormalized for querying; consistent with the document
    constraint)
  - `document_id` (FK -> knowledge_documents.id)
  - `document_version` (denormalized for traceability; NOT NULL)
- Chunk info
  - `chunk_no`: incrementing from 0 (NOT NULL)
  - `chunk_key`: stable identifier (nullable; e.g.
    `{doc_key}:{version}:{chunk_no}`)
  - `content_hash` (nullable)
  - `text_preview`: short preview (nullable, <= 512 recommended)
  - `text_artifact_key`: full-text storage key (nullable)
- Location and structure
  - `start_offset` / `end_offset` (nullable, character offsets)
  - `page_no` (nullable)
  - `section_path` (nullable, e.g. `["H1","H2"]`)
  - `bbox_json` (nullable, PDF coordinates)
  - `source_meta_json` (nullable: table/code/image references, etc.)
- Statistics
  - `char_count` (nullable)
  - `token_count` (nullable)
- Vector mapping and index status
  - `embedding_model_ref` (nullable; defaults inherited from
    knowledge/default or the index)
  - `vector_ref`: vector-store primary key / reference (nullable, filled
    after write)
  - `indexed_at` (nullable)
  - `index_status`: `pending | indexed | failed` (NOT NULL default pending)
  - `index_error` (nullable)
- Audit
  - `created_at`, `updated_at`

### 3.3 Key constraints and indexes
- UNIQUE:
  - `(tenant_id, workspace_id, document_id, chunk_no, document_version)`
- Indexes:
  - `(tenant_id, workspace_id, knowledge_id, document_id)`
  - `(tenant_id, workspace_id, knowledge_id, index_status)`
  - `(tenant_id, workspace_id, knowledge_id, updated_at DESC)`

---

## 4. knowledge_indexes (index configuration and mapping)

### 4.1 Design notes
- A knowledge base can have multiple indexes (different embeddings /
  providers / retrieval configurations)
- An index records: vector dimension, distance metric, collection/partition
  strategy, build version, statistics
- Supports gradual rollout: `is_primary` + `status`

### 4.2 Fields (recommended)
- Identity and isolation
  - `id` PK
  - `tenant_id`, `workspace_id` (NOT NULL)
  - `knowledge_id` (FK -> knowledge.id)
  - `name` (NOT NULL)
  - `is_primary` (NOT NULL default false)
- Provider/storage mapping
  - `provider`: `milvus | pgvector | elastic | other` (NOT NULL)
  - `endpoint_ref` (nullable, references gateway configuration)
  - `collection_name` (nullable)
  - `partition_strategy` (nullable: `tenant|workspace|knowledge|none`)
  - `namespace` (nullable: logical isolation)
- Embedding/retrieval configuration
  - `embedding_model_ref` (NOT NULL)
  - `dimension` (NOT NULL)
  - `metric_type` (NOT NULL: `cosine | ip | l2`)
  - `index_params_json` (nullable: index-build parameters)
  - `search_params_json` (nullable: search parameters, e.g. ef/top_k)
  - `reranker_ref` (nullable)
  - `filters_json` (nullable: default filter policy)
- Build and statistics
  - `status`: `draft | building | ready | failed | disabled` (NOT NULL)
  - `build_version` (NOT NULL default 1, incremented on rebuild)
  - `last_build_at` (nullable)
  - `doc_count` (NOT NULL default 0)
  - `chunk_count` (NOT NULL default 0)
  - `vector_count` (NOT NULL default 0)
  - `last_error_code` (nullable)
  - `last_error_message` (nullable)
- Audit
  - `created_by`, `updated_by`, `created_at`, `updated_at`, `deleted_at`

### 4.3 Key constraints and indexes
- UNIQUE:
  - `(tenant_id, workspace_id, knowledge_id, name)`
- Indexes:
  - `(tenant_id, workspace_id, knowledge_id, status)`
  - `(tenant_id, workspace_id, knowledge_id, is_primary)`
  - `(tenant_id, workspace_id, updated_at DESC)`

> Guarantee `is_primary` transactionally: only one primary=true per
> knowledge base.

---

## 5. Recommended Object-Storage Key Layout (optional but strongly advised)
- Raw file: `tenants/{tenant}/workspaces/{ws}/knowledge/{ds}/raw/{file_id}`
- Extracted text: `.../docs/{doc_id}/v{version}/raw_text.txt`
- Parsed structure: `.../docs/{doc_id}/v{version}/parsed.json`
- Chunk full text: `.../chunks/{chunk_id}.txt`
- Run logs (when tied to a run): `.../runs/{run_id}/...`

---

## 6. Vector-Store Mapping Recommendations (Milvus reference)
- Collection granularity: `tenant` or `workspace` (depending on scale)
- Filter dimensions: `workspace_id + knowledge_id + document_id + chunk_id`
- The chunk table keeps `vector_ref` to support reclamation/rebuild

---

## 7. Migration Guidance
- Land the table structures and indexes first
- Then implement the pipeline: state transitions for document.status and
  chunk.index_status
- Then implement index builds: increment knowledge_indexes.build_version and
  write statistics back
