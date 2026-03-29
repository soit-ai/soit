# ENGINEERING_GUIDE.md (SOIT Engineering Standard)

This document is **mandatory**. It defines engineering rules that keep SOIT stable for years:
- Kernel is stable and contract-first
- Domains evolve quickly without breaking kernel contracts
- Everything is scoped by `tenant_id + workspace_id`
- Everything executable is traceable (`run/run_step/run_cost_entries/run_artifact`)
- Everything external goes through ports
- Specs (JSON Schema) are the source of truth

> Language policy
> - Product/docs may be Chinese
> - \*\*Code comments and git commit messages MUST be English\*\*

---

## Project structure (authoritative)

All runtime code lives in the Python package **`app/`**. Within it, SOIT is organized into **four layers**:

1. **app/api/** (API & transport)
   - FastAPI routers/controllers, request parsing, response envelopes
   - SSE / WebSocket transport, OpenAPI
   - dependency wiring and composition happens here (thin)
2. **app/modules/** (business domains, fast iteration)
   - domain logic + use-cases (services)
   - repositories (persistence boundary) and domain schemas
   - MUST call external systems via kernel ports (interfaces)
3. **app/kernel/** (stable kernel, contract-first)
   - contracts, scope, policies, execution semantics, trace, registry, security, specs
   - gateway interfaces + enforcement policies
   - MUST NOT depend on FastAPI routers, domain tables/models, or provider SDKs
4. **app/adapters/** (infrastructure implementations)
   - implements kernel gateway interfaces (LLM/vector/storage/secrets/tools/db/telemetry)
   - contains provider SDK calls and infra details

**Rule of thumb:** if a file can be replaced without changing core semantics, it does **not** belong in `app/kernel/`.

---

## 0. Non‑negotiables

1. **Spec‑First**
   - Any new capability MUST start with a spec update under `app/kernel/specs/`.
   - Spec changes must include examples.
   - Runtime must validate incoming spec JSON against schema.

2. **Scope‑By‑Default**
   - Workspace resources MUST be isolated by `tenant_id + workspace_id`.
   - Business APIs MUST NOT accept `tenant_id/workspace_id` as free parameters.
   - Scope is resolved by `RequestContext` only.

3. **Trace Everything**
   - Any executable action MUST create a `run` and at least one `run_step`.
   - Large payloads MUST be stored as artifacts (object storage) and referenced by key.
   - Costs MUST be written to `run_cost_entries`.

4. **Port‑Only**
   - LLM / tools / MCP / vector DB / object storage / secrets MUST be accessed via ports.
   - Ports enforce retry/timeout/audit/rate-limit consistently.

5. **Immutable Versions**
   - `agent_version`, `workflow_version`, `plugin_version` are immutable.
   - Publish/rollback only moves pointers (e.g., `current_version_id`).

6. **Secure‑by‑default**
   - Egress is deny-by-default.
   - Secrets are **references** only (Vault/KMS), never plaintext.
   - High-risk runtimes are disabled unless explicitly enabled.

---

## 1. Dependency Direction (import rules)

Allowed dependency directions (top -> bottom):

- `app/api/*             -> app/modules/*`
- `app/api/*             -> app/kernel/*` (contracts/policies only)
- `app/modules/*         -> app/kernel/*`
- `app/adapters/*        -> app/kernel/ports/*` (implements gateway interfaces)
- `app/kernel/*          -> app/kernel/*`

Forbidden (must fail code review):

- `app/kernel/*          -> app/modules/*`
- `app/kernel/*          -> app/api/*`
- `app/modules/*         -> app/api/*`
- Any module importing other modules' **domain models** directly (avoid cycles; depend on contracts/ports instead)

**Enforcement**
- Code review is mandatory.
- Add an import-lint rule (recommended) to fail forbidden imports.

## 2. Repository boundaries

### 2.1 Kernel (stable)
Kernel owns:
- contracts, scope, policy, execution semantics, trace schema
- gateway interfaces and security guardrails
- spec schemas and registry mechanism

Kernel MUST NOT:
- include product/business rules
- depend on FastAPI, ORM implementations, or provider SDKs
- depend on module tables or module services

### 2.2 Modules (domains, fast iteration)
Modules own:
- domain models (SQLModel), domain schemas (Pydantic), repositories, services/use-cases
- state machines for domain objects (knowledge ingestion, workflow versions, plugin installations)

Modules MUST:
- call external systems only via kernel ports
- use scope-aware repositories
- keep HTTP concerns out of modules (no FastAPI routers in modules)

### 2.3 App/API (transport & composition)
API layer owns:
- routers/controllers, request parsing, response envelopes
- permission checks (call kernel policy)
- orchestration across modules (thin)

API layer MUST NOT:
- contain persistence logic
- implement domain algorithms

## 3. Identity & Scope (tenant + workspace)

### 3.1 RequestContext
Each request must resolve:
- `tenant_id`, `user_id` from JWT/session
- `workspace_id` from header/path
- membership + role checks

All services accept `ctx: RequestContext`.

### 3.2 Scope-aware repositories
All workspace-scoped queries must enforce:

`WHERE tenant_id = ctx.tenant_id AND workspace_id = ctx.workspace_id`

No exceptions unless:
- explicit tenant-admin scope is required, AND
- policy check is performed, AND
- code is reviewed with security in mind.

### 3.3 DB constraints
- Workspace tables: `(tenant_id, workspace_id)` NOT NULL.
- UNIQUE indexes must include `(tenant_id, workspace_id, ...)`.

### 3.4 RBAC guard usage (service layer)
Services MUST use guard decorators for authorization instead of hard-coded checks:

- Use `rbac_guard(resource_type, action, ...)` for resource-level actions:
  `create | read | update | delete | run`.
- Use `workspace_guard("read" | "write" | "owner" | "admin")` for workspace/tenant checks.
- For create actions without a stable id yet, supply `resource_id_resolver` to derive a placeholder
  (example: `new:<workspace_id>`), and optionally `owner_id_resolver`.
- Prefer decorators in module services; API layer stays thin and does not enforce permissions directly.

---

## 4. API conventions

### 4.1 Success envelope
All API success responses SHOULD be:

```json
{
  "success": true,
  "code": "OK",
  "message": "OK",
  "data": { "any": "json" },
  "request_id": "req_...",
  "run_id": "run_..."
}
```

### 4.2 Error envelope
All API errors MUST be:

```json
{
  "success": false,
  "code": "ENUM_CODE",
  "message": "Human readable",
  "details": { "any": "json" },
  "request_id": "req_...",
  "run_id": "run_..."
}
```

### 4.3 Pagination
Cursor-based:
- request: `page_size`, `page_token`
- response: `items`, `next_page_token`

### 4.4 Idempotency
Write APIs SHOULD support `Idempotency-Key`.
Gateway retries MUST be safe or disabled.

---

## 4.5 Directory placement rules (quick)

- HTTP request/response schemas: `app/api/v1/schemas/*`
- Domain/internal schemas (not part of HTTP): `app/modules/<domain>/**/schemas.py`
- Cross-layer stable contracts: `app/kernel/contracts/*`
- Dependency wiring / container: `app/wiring/*`
- Settings & feature flags: `app/settings/*`
- Provider implementations: `app/adapters/*`
- Specs (JSON Schema): `app/kernel/specs/v1/*`

## 5. Execution & Trace standard

SOIT’s **core execution model** is part of the **platform bedrock** and belongs to `app/kernel/`.
These four concepts MUST be stable across years and versions:

- **Run**: one end-to-end execution (a chat turn, an agent run, a workflow run, a batch job)
- **Step**: one atomic, observable unit inside a run (LLM call, retrieval, tool call, node execution, memory write)
- **Artifact**: any large payload or file produced/consumed by a run/step (stored outside DB; DB stores references)
- **Cost**: normalized accounting records attached to a run and (optionally) a step

> Design intent: **Modules iterate fast**, but **Run/Step/Artifact/Cost semantics do not change**.
> If you change these semantics, you are changing the platform.

### 5.1 Definitions & invariants (MUST)

#### 5.1.1 Run
A **Run** is the single “trace root” for an executable request.

**MUST**
- `run_id` is generated once and is immutable.
- Every externally visible execution path returns/attaches `run_id` (API response header/body).
- Run has **bounded summaries** only (`input_summary`, `output_summary`).
- Run status is one of: `queued | running | succeeded | failed | canceled` (or a compatible superset).

**SHOULD**
- Record `kind`: `chat | workflow | agent | tool | batch` (string enum; keep stable).
- Record `started_at`, `ended_at`, `duration_ms`.

#### 5.1.2 Step
A **Step** is a child of a Run and represents one atomic unit that can be retried, inspected, and costed.

**MUST**
- Each Step references its parent `run_id`.
- Steps are **append-only** (never rewrite history; create a new step if you must re-execute).
- Each step has `type` (stable enum): `llm | retrieval | rerank | tool | workflow_node | agent_plan | memory_write | io | other`.
- Each step stores only **bounded** summaries; large payloads go to artifacts.

**SHOULD**
- Step links to its logical owner (`workflow_node_id`, `tool_ref`, `model_ref`, etc.) via refs.

#### 5.1.3 Artifact
An **Artifact** is an addressable blob/file produced or consumed during execution.

**MUST**
- DB stores **metadata + reference only**: `artifact_id`, `run_id`, optional `step_id`, `kind`, `mime`, `size_bytes`, `storage_key`, `sha256`.
- Artifact content is stored in object storage (S3/MinIO/etc.) via Storage Port.
- Artifact is immutable once written (new version => new artifact_id).

**SHOULD**
- Enforce tenant/workspace scoping via key prefix:
  `artifacts/<tenant>/<workspace>/<run_id>/<artifact_id>/*`

#### 5.1.4 Cost
A **Cost** record normalizes all billable/trackable resource usage.

**MUST**
- Costs are written for any step that calls external resources (LLM/tool/egress) or consumes metered compute.
- Cost is recorded in a stable, queryable form:
  - `currency` (e.g. USD)
  - `amount` (decimal)
  - `unit` (e.g. tokens, requests, seconds, bytes)
  - `quantity` (decimal)
  - `provider` / `model_ref` / `tool_ref` when applicable
- Cost is attributable to **Run** and optionally a **Step** (`run_id`, nullable `step_id`).

**SHOULD**
- Store breakdown fields for LLM: `prompt_tokens`, `completion_tokens`, `total_tokens`.

### 5.2 Lifecycle (MUST)

A compliant execution path follows this order:

1. **Resolve RequestContext** (tenant/workspace/user)  
2. **Create Run** (status `queued` or `running`)  
3. For each unit of work: **append Step** (status `running` -> terminal)  
4. Store large data as **Artifacts** and link from Run/Step  
5. Write **Cost** records per step (or aggregated per run, but still traceable)  
6. End Run (terminal status + timestamps)

**Failure rules**
- A step failure MUST NOT delete previous steps/artifacts/costs.
- Run status `failed` MUST preserve the last error summary and the step that failed (by id).

### 5.3 What requires `run_step` (MUST)
A `run_step` MUST be created for:
- LLM call
- retrieval / rerank
- tool call (HTTP / Function / MCP)
- workflow node execution
- agent planning / memory writes (summary at minimum)
- any external egress boundary crossing (even if cached)

### 5.4 Payload storage rule (MUST)
- DB stores summaries + references (bounded)
- long content/files/logs -> object storage + `run_artifact`

Suggested limits (tunable):
- `run_step.input_summary/output_summary` <= 8KB
- `run.input_summary/output_summary` <= 8KB

### 5.5 Kernel ownership & placement (authoritative)
These semantics are kernel-owned and MUST live under `app/kernel/`:

- `app/kernel/execution/`  
  execution primitives, state machine, id generation helpers (if any)
- `app/kernel/trace/`  
  persistence contracts for run/step/artifact/cost + exporter interfaces
- `app/kernel/specs/v1/`  
  JSON Schemas for `run`, `run_step`, `run_artifact`, `run_cost_entries` payloads

Modules and API may **use** these contracts, but MUST NOT redefine meanings.

### 5.6 Review & CI gates (recommended)
Add checks that fail the build if:
- Any execution path returns success without creating a run + at least one step
- Any step stores payloads beyond the configured summary limits
- Cross-tenant/workspace artifact keys are possible
- Costs are missing for metered boundaries (LLM/tool/egress)


## 6. Ports & Ports (policy enforcement point)

SOIT uses **ports** as the stable interfaces (see `app/kernel/ports/*`).
Adapters implement ports, and `app/wiring/*` wires them into module services.

Policy enforcement MUST happen consistently at the boundary:
- timeout
- retry policy (idempotent only)
- audit logging (request_id/run_id/step_id)
- rate limiting (tenant/workspace)
- secrets resolution via secrets port (refs only)
- egress policy checks (deny-by-default)

**Rule:** modules never call provider SDKs directly; they call ports only.

---



## Plugins

SOIT plugins are **runtime artifacts**. A plugin installation contributes:
- one `plugin_spec` (validated by JSON Schema)
- optionally, **exported tools** (each has a `tool_spec`)
- optionally, **exported workflow nodes** (each has a `node_spec`)
- optional runtime config (stored in `manifest.json` and/or installation `config_json`)

### Filesystem layout (authoritative)

Runtime plugin artifacts are stored on filesystem under `Settings.plugins_dir` (default: `./var/plugins`):

- packages: `var/plugins/packages/<tenant>/<workspace>/<name>/<version>/...`
- installs:  `var/plugins/installed/<tenant>/<workspace>/<name>/<version>/...`

### Plugin package format (zip)

A minimal plugin zip:

```
manifest.json
spec.json
files/
  tools/
    <tool_name>.json
  nodes/
    <node_name>.json
```

Rules:
- `spec.json` MUST validate against `kernel/specs/v1/plugin_spec.schema.json`
- `spec.exports.tools` is a list of **tool refs**, e.g. `tool:http:ticket_create`
- For each exported tool ref, SOIT will load the tool spec from:
  `files/tools/<tool_name>.json` (where `<tool_name>` is the last segment of the tool ref)
- `spec.exports.workflow_nodes` is a list of **node refs**, e.g. `node:tool:health_check`
- For each exported node ref, SOIT will load the node spec from:
  `files/nodes/<node_name>.json` (where `<node_name>` is the last segment of the node ref)

### Enable/disable

- `manifest.json` carries `enabled: true|false` (restart-safe).
- `POST /api/v1/plugins/{plugin_id}/enabled` updates both DB (`config_json.enabled`) and FS (`manifest.json.enabled`).

### Runtime registry & tool routing

- Marketplace installs register **plugins** and **tools** into the in-process registry (`app/kernel/registry`).
- On startup, `PluginRuntimeLoader` reloads all **enabled** installed plugins into registry.
- `ToolPort` uses `RegistryToolRouterPort`:
  - If a `tool_ref` exists in registry (`kind="tool"`), it resolves `tool_spec` and dispatches to the right adapter.
  - Otherwise it falls back to raw HTTP tool invocation.

Runtime introspection endpoints:
- `POST /api/v1/plugins/runtime/reload`
- `GET  /api/v1/plugins/runtime/tools`


## 7. Specs & Refs


### 7.1 JSON Schemas
- Specs live under `app/kernel/specs/v1`.
- Runtime MUST validate spec_json/manifest_json/graph_json against schema.

### 7.2 Reference models (Refs)
All cross-resource references MUST follow:
`app/kernel/specs/v1/refs.schema.json`

Examples:
- `model:openai:gpt-4.1`
- `knowledge:kb_support`
- `tool:http:ticket_create`
- `node:tool:health_check`
- `wf:rag_answer`
- `secret:zendesk_token`

---

## 8. Database migrations

- Use Alembic migrations (do not apply raw SQL directly in production).
- Migration files must be reviewed.
- Each migration must be reversible when feasible.
- For large tables, avoid long locks (use concurrent index creation when possible).

---

## 9. Testing (minimum bar)

Mandatory tests:
- cross-tenant access returns 403/404
- cross-workspace access returns 403/404
- spec validation rejects invalid JSON
- any execution produces run + steps
- gateway mocks allow deterministic tests

Recommended:
- contract tests for ports
- smoke tests for docker-compose

---

## 10. CI quality gates (minimum)

Backend:
- ruff (lint/format)
- mypy (types)
- pytest (unit)
- migration sanity checks (alembic head)

Frontend:
- typecheck
- lint/format
- build

Security (recommended):
- dependency scanning
- secret scanning

---

## 11. PR checklist (must complete)

- [ ] Spec updated (if new capability) + examples added
- [ ] Scope enforced (tenant/workspace) + tests added
- [ ] run/run_step emitted for new execution paths
- [ ] gateway used for any external call
- [ ] breaking-change impact assessed
- [ ] CI passes
