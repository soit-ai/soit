# KERNEL_V1_DATA_MODEL (Skeleton)

This document defines the **Kernel v1 minimal data model skeleton**.
It is designed to be stable for years and to support:
- `tenant_id + workspace_id` isolation
- immutable versioning
- unified execution traces (run/step/artifact/cost)
- dataset pipeline (document/chunk/index) and future extension

> Note: columns may be extended later, but the **core keys, constraints and index patterns**
> should remain stable to minimize migrations.

---

## 0. Global conventions

- IDs: ULID preferred (sortable), stored as TEXT or UUID.
- Timestamps: `created_at`, `updated_at` are `timestamptz`.
- Soft delete: `deleted_at` optional but recommended for high-value resources.
- Scope: workspace-scoped tables must include `tenant_id` + `workspace_id`.

---

## 1. Identity (tenant/workspace/user)

### tenants
- `id` PK
- `name`, `plan`
- `created_at`

### workspaces
- `id` PK
- `tenant_id` FK → tenants.id
- `name`
- UNIQUE `(tenant_id, name)`
- INDEX `(tenant_id, created_at DESC)`

### users
- `id` PK
- `email` UNIQUE
- `password_hash`
- `created_at`

### tenant_memberships
- PK `(tenant_id, user_id)`
- `role` (Owner/Admin/Dev/Viewer)
- `created_at`

### workspace_memberships
- PK `(tenant_id, workspace_id, user_id)`
- `role` (Owner/Admin/Dev/Viewer)
- `created_at`

---

## 2. App Center (apps and immutable versions)

### apps
Workspace-scoped.
- `id` PK
- `tenant_id`, `workspace_id`
- `type` (chat/bot/workflow/agent/app)
- `status` (active/archived)
- `visibility` (private/workspace/public)
- `name`, `description`
- `current_version_id` (nullable)
- UNIQUE `(tenant_id, workspace_id, name)`
- INDEX `(tenant_id, workspace_id, type)`

### app_versions (immutable)
- `id` PK
- `tenant_id`, `workspace_id`, `app_id` FK → apps.id
- `spec_json` (AppSpec)
- `created_by`, `created_at`
- INDEX `(tenant_id, workspace_id, app_id, created_at DESC)`

---

## 3. Workflow (definition and immutable versions)

Workflow definitions are stored in `apps/app_versions` with:
- `apps.type = WORKFLOW`
- `app_versions.spec_schema = workflow.v1`

---

## 4. Runtime Trace (unified execution)

### runs
Workspace-scoped.
- `id` PK
- `tenant_id`, `workspace_id`
- `mode` (chat/bot/workflow/agent)
- `app_id` FK → apps.id (required)
- `app_version_id` FK → app_versions.id (required)
- `app_type` (optional redundancy)
- `status` (queued/running/succeeded/failed/canceled)
- `input_summary`, `output_summary` (bounded)
- `started_at`, `ended_at`
- INDEX `(tenant_id, workspace_id, started_at DESC)`

### run_steps
- `id` PK
- `tenant_id`, `workspace_id`, `run_id` FK → runs.id
- `step_type` (llm/retrieve/tool/node/plan)
- `node_id` nullable
- `status`, `started_at`, `ended_at`
- `input_summary`, `output_summary` (bounded)
- `metrics_json` (tokens/latency/http_status/vector_count)
- INDEX `(tenant_id, workspace_id, run_id)`

### run_artifacts
- `id` PK
- `tenant_id`, `workspace_id`, `run_id` FK → runs.id
- `type` (file/log/blob/json)
- `storage_key`
- `meta_json` (mime/size/hash)
- INDEX `(tenant_id, workspace_id, run_id)`

### run_cost_entries
- `id` PK
- `run_id` FK
- `step_id` nullable
- `tenant_id`, `workspace_id`
- `currency`, `amount`
- `unit`, `quantity`
- `provider`, `model_ref`, `tool_ref`
- `prompt_tokens`, `completion_tokens`, `total_tokens`
- `created_at`
- INDEX `(tenant_id, workspace_id, run_id)`

---

## 5. Dataset (knowledge base)

Kernel-level dataset skeleton. For detailed design see:
- `docs/architecture/DATASET_DATA_MODEL.md`

### dataset
Workspace-scoped.
- `id` PK
- `tenant_id`, `workspace_id`
- `name`, `type`, `status`
- `settings_json`, `chunking_json`, `retrieval_json`
- `default_embedding_model_ref`, `default_index_id`
- UNIQUE `(tenant_id, workspace_id, name)`

### dataset_documents
Workspace-scoped.
- `id` PK
- `tenant_id`, `workspace_id`, `dataset_id`
- `doc_key`, `version`, `is_latest`
- `source_type`, `source_uri`, `file_id`
- `status`, `error_code`, `retry_count`
- UNIQUE `(tenant_id, workspace_id, dataset_id, doc_key, version)`
- INDEX `(tenant_id, workspace_id, dataset_id, is_latest)`

### dataset_chunks
Workspace-scoped.
- `id` PK
- `tenant_id`, `workspace_id`, `dataset_id`, `document_id`
- `document_version`, `chunk_no`
- `text_preview`, `text_artifact_key`
- `vector_ref`, `index_status`
- UNIQUE `(tenant_id, workspace_id, document_id, chunk_no, document_version)`

### dataset_indexs
Workspace-scoped.
- `id` PK
- `tenant_id`, `workspace_id`, `dataset_id`
- `name`, `provider`
- `embedding_model_ref`, `dimension`, `metric_type`
- `index_params_json`, `search_params_json`
- `status`, `build_version`
- UNIQUE `(tenant_id, workspace_id, dataset_id, name)`

---

## 6. Tools & Plugins & Secrets

### tools (workspace-scoped)
- `id` PK
- `tenant_id`, `workspace_id`
- `name`
- `spec_json` (ToolSpec)
- UNIQUE `(tenant_id, workspace_id, name)`

### plugins (tenant-scoped install)
- `id` PK
- `tenant_id`
- `name`, `publisher`
- `status`

### plugin_versions (immutable)
- `id` PK
- `plugin_id` FK → plugins.id
- `manifest_json` (PluginSpec)
- `digest`, `signature`
- `created_at`

### secrets (tenant-scoped)
- `id` PK
- `tenant_id`
- `name`
- `provider` (vault/kms/local)
- `ref` (vault path or key id; never plaintext)
- UNIQUE `(tenant_id, name)`

---

## 7. Index patterns (hard rules)

- Any UNIQUE constraint for workspace resources MUST include `(tenant_id, workspace_id, ...)`.
- Any listing query MUST have an index starting with `(tenant_id, workspace_id, ...)`.
- For trace tables, ensure fast lookup by `(tenant_id, workspace_id, run_id)`.
