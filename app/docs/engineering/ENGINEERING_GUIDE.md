# ENGINEERING_GUIDE.md (SOIT Kernel Standard)

This document is **mandatory**. It defines engineering rules that keep SOIT stable for years:
- Kernel is stable and compatibility-first
- Domains evolve quickly without breaking kernel contracts
- Everything is scoped by `tenant_id + workspace_id`
- Everything executable is traceable (`run/run_step/run_cost/run_artifact`)
- Everything external goes through gateways
- Specs (JSON Schema) are the source of truth

> Language policy
> - Product/docs may be Chinese
> - **Code comments and git commit messages MUST be English**

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
   - Costs MUST be written to `run_cost`.

4. **Gateway‑Only**
   - LLM / tools / MCP / vector DB / object storage / secrets MUST be accessed via gateways.
   - Gateways enforce retry/timeout/audit/rate-limit consistently.

5. **Immutable Versions**
   - `app_version`, `workflow_version`, `plugin_version` are immutable.
   - Publish/rollback only moves pointers (e.g., `current_version_id`).

6. **Secure‑by‑default**
   - Egress is deny-by-default.
   - Secrets are **references** only (Vault/KMS), never plaintext.
   - High-risk runtimes are disabled unless explicitly enabled.

---

## 1. Dependency Direction (import rules)

Allowed dependency directions:

- `modules/entrypoints/*  -> modules/domains/*`
- `modules/*              -> kernel/*`
- `adapters/*             -> kernel/gateways/*` (implementations plugged into gateways)
- `kernel/*               -> kernel/*`

Forbidden:

- `kernel/* -> modules/*`
- `modules/domains/*` importing other domains' **models** directly (avoid cycles)
- `modules/entrypoints/*` doing complex domain logic (must call domain services)

**Enforcement**
- Code review is mandatory.
- Add an import-lint rule (recommended) to fail forbidden imports.

---

## 2. Repository boundaries

### 2.1 Kernel (stable)
Kernel owns:
- contracts, scope, policy, execution semantics, trace schema
- gateways and security guardrails
- spec schemas and registry mechanism

Kernel MUST NOT:
- include product/business rules
- depend on domain tables or domain services

### 2.2 Domains (fast iteration)
Domains own:
- domain models (SQLModel), schemas (Pydantic), repositories, services
- state machines for domain objects (dataset pipeline, workflow versions, market listings)

Domains MUST:
- call external systems only via gateways
- use scope-aware repositories

### 2.3 Entrypoints (API layer)
Entrypoints own:
- routers/controllers, request parsing, response envelopes
- permission checks (call kernel policy)
- orchestration across domains (thin)

Entrypoints MUST NOT:
- contain persistence logic
- implement domain algorithms

---

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

---

## 4. API conventions

### 4.1 Error envelope
All API errors MUST be:

```json
{
  "error": {
    "code": "ENUM_CODE",
    "message": "Human readable",
    "details": { "any": "json" }
  },
  "request_id": "req_...",
  "run_id": "run_..."
}
```

### 4.2 Pagination
Cursor-based:
- request: `page_size`, `page_token`
- response: `items`, `next_page_token`

### 4.3 Idempotency
Write APIs SHOULD support `Idempotency-Key`.
Gateway retries MUST be safe or disabled.

---

## 5. Execution & Trace standard

### 5.1 What requires run_step
- LLM call
- retrieval / rerank
- tool call (HTTP / Function / MCP)
- workflow node execution
- agent planning / memory writes (summary at minimum)

### 5.2 Payload storage rule
- DB stores summaries + references (bounded)
- long content/files/logs -> object storage + `run_artifact`

Suggested limits (tunable):
- `run_step.input_summary/output_summary` <= 8KB
- `run.input_summary/output_summary` <= 8KB

---

## 6. Gateways (policy enforcement point)

All gateways MUST implement:
- timeout
- retry policy (idempotent only)
- audit logging (request_id/run_id/step_id)
- rate limiting (tenant/workspace)
- secrets resolution via secrets gateway (refs only)
- egress policy checks (deny-by-default)

---

## 7. Specs & Refs

### 7.1 JSON Schemas
- Specs live under `app/kernel/specs/v1`.
- Runtime MUST validate spec_json/manifest_json/graph_json against schema.

### 7.2 Reference models (Refs)
All cross-resource references MUST follow:
`app/kernel/specs/v1/refs.schema.json`

Examples:
- `model:openai:gpt-4.1`
- `ds:kb_support`
- `tool:http:ticket_create`
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
- contract tests for gateways
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
- [ ] backward compatibility considered
- [ ] CI passes
