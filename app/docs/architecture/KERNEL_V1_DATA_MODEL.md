# KERNEL_V1_DATA_MODEL (Skeleton)

This document defines the **Kernel v1 minimal data model skeleton**.
It is designed to be stable for years and to support:
- `tenant_id + workspace_id` isolation
- immutable versioning
- unified execution traces (run/step/artifact/cost)
- knowledge ingestion and retrieval pipeline

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

## 2. Agents (primary business object)

### agents
Workspace-scoped.
- `id` PK
- `tenant_id`, `workspace_id`
- `status` (active/archived)
- `visibility` (private/workspace/public)
- `name`, `description`, `icon_url`, `category`
- `is_public`, `featured`
- `downloads_count`, `rating`, `reviews_count`, `published_at`
- `current_version_id` (nullable)
- `published_version_id` (nullable)
- UNIQUE `(tenant_id, workspace_id, name)`
- INDEX `(tenant_id, workspace_id, status)`

### agent_versions (immutable)
- `id` PK
- `tenant_id`, `workspace_id`, `agent_id`
- `spec_json` (agent.v1)
- `created_by`, `created_at`
- INDEX `(tenant_id, workspace_id, agent_id, created_at DESC)`

---

## 3. Workflow (definition and immutable versions)

Workflow definitions are stored in dedicated `workflows/workflow_versions` tables:
- `workflows.name`, `description`, `summary`
- `workflows.visibility`, `icon_url`, `category`, `tags`
- `workflows.owner_user_id`
- `workflows.current_version_id`
- `workflows.published_version_id`
- `workflow_versions.spec_schema = workflow.v1`

---

## 4. Runtime Trace (unified execution)

### threads
Workspace-scoped session container.
- `id` PK
- `tenant_id`, `workspace_id`
- `agent_id` nullable FK → agents.id
- `thread_type`, `source`, `status`
- `title`, `summary`
- `system_prompt`
- `default_model_ref`, `default_temperature`, `default_max_tokens`, `default_top_p`
- `context_window`, `max_history_messages`, `max_history_chars`
- `message_count`
- `last_message_at`, `last_user_message_at`, `last_assistant_message_at`
- `latest_run_id`
- `knowledge_config_json`, `tool_config_json`
- `metadata_json`
- `pinned_at`, `archived_at`, `deleted_at`
- INDEX `(tenant_id, workspace_id, updated_at DESC)`
- INDEX `(agent_id, status, updated_at DESC)`

### thread_messages
Workspace-scoped message ledger.
- `id` PK
- `tenant_id`, `workspace_id`
- `thread_id` FK → threads.id
- `run_id` nullable FK → runs.id
- `task_id` nullable FK → tasks.id
- `response_id` nullable FK → responses.id
- `parent_message_id` nullable self-FK
- `sequence_no` within thread
- `role`, `message_type`, `status`
- `content`, `content_json`, `summary`
- `model_ref`, `tokens_prompt`, `tokens_completion`, `finish_reason`
- `citations_json`, `attachments_json`, `tool_calls_json`
- `error_code`, `error_message`
- `metadata_json`
- `created_at`, `edited_at`, `deleted_at`
- UNIQUE `(thread_id, sequence_no)`
- INDEX `(thread_id, created_at)`

### runs
Workspace-scoped.
- `id` PK
- `tenant_id`, `workspace_id`
- `mode` (chat/workflow/agent/knowledge/memory/task-domain modes)
- `subject_kind` / `subject_id` / `subject_version_id` (primary execution subject)
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

## 5. Knowledge

Kernel-level knowledge skeleton. Product, API, and persistence table names are
now unified as `knowledge`.

Public API rules:
- create/read flows use `knowledge_type` as the stable upstream field
- `source_type` is retained in responses as a compatibility alias for existing UI code
- internal storage details must not leak into new product docs or APIs

For detailed design see:
- `app/app/app/modules/knowledge/KNOWLEDGE_DATA_MODEL.md`

### knowledge base (`knowledge`)
Workspace-scoped.
- `id` PK
- `tenant_id`, `workspace_id`
- `name`, `type`, `status`
- `settings_json`, `chunking_json`, `retrieval_json`
- `default_embedding_model_ref`, `default_index_id`
- UNIQUE `(tenant_id, workspace_id, name)`

### knowledge documents (`knowledge_documents`)
Workspace-scoped.
- `id` PK
- `tenant_id`, `workspace_id`, `knowledge_id`
- `doc_key`, `version`, `is_latest`
- `source_type`, `source_uri`, `file_id`
- `status`, `error_code`, `retry_count`
- UNIQUE `(tenant_id, workspace_id, knowledge_id, doc_key, version)`
- INDEX `(tenant_id, workspace_id, knowledge_id, is_latest)`

### knowledge chunks (`knowledge_chunks`)
Workspace-scoped.
- `id` PK
- `tenant_id`, `workspace_id`, `knowledge_id`, `document_id`
- `document_version`, `chunk_no`
- `text_preview`, `text_artifact_key`
- `vector_ref`, `index_status`
- UNIQUE `(tenant_id, workspace_id, document_id, chunk_no, document_version)`

### knowledge indexes (`knowledge_indexes`)
Workspace-scoped.
- `id` PK
- `tenant_id`, `workspace_id`, `knowledge_id`
- `name`, `provider`
- `embedding_model_ref`, `dimension`, `metric_type`
- `index_params_json`, `search_params_json`
- `status`, `build_version`
- UNIQUE `(tenant_id, workspace_id, knowledge_id, name)`

---

## 6. Tools, Plugins, and Secrets

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
- `spec_json` stores the capability contract and compatibility surface
- `manifest_json` stores package/release metadata
- installation `config_json` stores environment-specific enablement and runtime config

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
