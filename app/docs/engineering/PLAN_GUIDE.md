# SOIT Development Plan (Roadmap & Backlog)
> Version: v1.0  
> Date: 2026-01-04  
> Principle: Keep the **Kernel** long-term stable. Everything else should be extensible via **Plugins / Apps**. Decouple through **Gateway + Registry** so implementations are replaceable and evolvable.

---

## 1. Goals and Scope

### 1.1 Product Form Progression
- **Chat → Bot → Workflow → Agent → App/Workspace**
- All forms share the same foundation: Identity & Authorization, Multi-tenancy, Gateway abstractions, Plugin registry, Execution engine, and Observability.

### 1.2 Core Execution Bedrock (Run / Step / Artifact / Cost)

The **core execution model** is platform bedrock and MUST remain stable over time:

- **Run**: one end-to-end execution (chat turn / workflow run / agent run / batch job)
- **Step**: one atomic unit inside a run (LLM / retrieval / tool call / workflow node)
- **Artifact**: large payloads/files referenced by run/step (stored in object storage; DB stores refs)
- **Cost**: normalized metering attached to run and optionally a step (tokens/requests/seconds/bytes)

**Rule:** any successful execution path MUST create `run` and at least one `run_step`, and SHOULD write `run_cost_entries` for metered boundaries.


### 1.3 Suggested Boundary: Open-Source Kernel vs. Premium Add-ons
- **Open-source (priority):** Kernel + Gateway + Registry + Execution + Observability + foundational Chat/Bot/Workflow + foundational Dataset
- **Premium/Enterprise (later):** SSO/SAML, audit & compliance, guardrails policy center, private marketplace, billing & quotas, enterprise security boundary, advanced collaboration

---

## 2. Milestone Plan

> Priority: P0 (Must) / P1 (High) / P2 (Medium) / P3 (Low)

| Milestone | Deliverable | Core Packages | Priority | Key Dependencies |
|---|---|---|---|---|
| M0 Kernel Foundation | Long-term stable Kernel + Gateway + Registry + Execution Bedrock | Identity/RBAC, multi-tenant base tables, migrations, unified error codes, event bus, gateway interfaces, plugin registry & lifecycle, **Run/Step/Artifact/Cost core execution model**, SSE/streaming protocol, basic logging & TraceId | P0 | DB/config system, interface freeze |
| M1 Chat | Usable chat APIs (streaming) | session/message model, `provider:model` routing, streaming output, persistence & pagination, chat params (system/temperature/etc.), basic cost tracking | P1 | LLM Gateway, SSE |
| M2 Bot | Configurable and publishable bots | bot definition (prompt/tool permissions/model/params), versioning, publish & share, run history | P1 | Registry, Tools |
| M3 Dataset | Dataset ingestion + RAG retrieval loop | dataset management, upload/parse/chunk, embeddings, vector index, retrieval strategies, citation snippets, delete/rebuild strategies | P1 | Vector/Storage |
| M4 Tools & Connectors | Working tool plugin system | tool protocol (HTTP first), schema/permissions/cost, secret injection, auditing, minimal tool set (HTTP/time/random/etc.) | P1 | Secrets, Registry |
| M5 Workflow | Executable orchestration (nodes fully pluginized) | workflow definition/versioning, node plugins (LLM/Tool/Condition/Variable/HTTP), variable flow, run/retry/replay, run history & logs, import/export (YAML/JSON) | P1 | Execution engine, Node plugins |
| M6 Agent | Agent runtime (plan-execute-verify) | modular Planner/Executor/Verifier, memory interface, budgets & rate limits, failure recovery | P2 | Tools/Workflow, Memory |
| M7 Workspace & App | App-shaped delivery | workspace (projects/members/resources), app definition (UI + backend binding), publish/install, app-level permissions | P2 | Identity, Registry (App type) |
| M8 Enterprise Boundary | Enterprise security & compliance | SSO (OIDC)/SAML, org structure, audit logs, guardrails policy center, KMS/Vault, data isolation policies | P2 | Identity/Audit/Secrets |
| M9 SaaS Ops & Billing | SaaS operations capabilities | plans/quotas/usage, cost center, rate limiting, ops console, alerting | P3 | Metering, Observability |
| M10 Marketplace | Ecosystem distribution | marketplace listing, rating/review, signing verification, canary/compat strategy, private marketplace (enterprise) | P3 | Registry, signing/verification |

---

## 3. MVP (Minimum Viable Loop)

**Required MVP loop:**
1. **M0:** Identity + Gateway + Registry + **Execution Bedrock (Run/Step/Artifact/Cost)** + Observability (SSE)  
2. **M1:** Chat (multi-model routing + streaming + persistence)  
3. **M3:** Dataset (upload → chunk → vectorize → retrieve → cite)  
4. **M4:** Tools (HTTP tools + secret injection)  
5. **M5:** Workflow (basic node plugins + run history)

---

## 4. Backlog Feature Table (Task Breakdown Ready)

### 4.1 Multi-tenancy & Authorization
| Module | Feature | Priority | Acceptance Criteria |
|---|---|---|---|
| Tenant | tenant/project/workspace model | P0 | schema + APIs; isolation enforced |
| RBAC | roles (Owner/Admin/Dev/Viewer) + resource grants | P0/P1 | auth checks; correct denial paths |
| API Key | create/rotate/disable API keys | P0 | keys work and can be revoked |

### 4.2 Plugin System (Registry)
| Module | Feature | Priority | Acceptance Criteria |
|---|---|---|---|
| Plugin Types | ModelProvider / Tool / WorkflowNode / App | P0 | extensible types; unified metadata |
| Lifecycle | install/uninstall/enable/disable/upgrade | P0/P1 | compatibility checks; rollback optional |
| Versioning | versions/dependencies/compat matrix | P1 | dependency conflicts are readable |

### 4.3 Model Gateway (LLM Gateway)
| Feature | Priority | Acceptance Criteria |
|---|---|---|
| `provider:model` routing + capability declarations | P0 | choose provider/model and call correctly |
| unified request/response contracts | P0 | swapping adapters won’t break upper layers |
| SSE streaming | P0/P1 | stable consumption; proper disconnect handling |
| timeouts/retries/circuit breaking (minimal) | P1 | configurable; failures traceable |
| token/cost accounting | P1 | each call produces metrics records |

### 4.4 Tools Gateway
| Feature | Priority | Acceptance Criteria |
|---|---|---|
| tool schema (JSON Schema) + param validation | P1 | invalid inputs rejected |
| secret injection (headers/signature/etc.) | P1 | secrets never logged; injection correct |
| tool call auditing | P1 | calls are searchable |
| minimal tool set (HTTP/time/text utils) | P1 | supports Workflow/Agent flows |

### 4.5 Vector & Storage (Vector/Storage)
| Feature | Priority | Acceptance Criteria |
|---|---|---|
| Milvus adapter (Vector Gateway) | P1 | upsert/search/delete work |
| MinIO/S3 adapter (Storage Gateway) | P1 | upload/download/signed URL work |
| document metadata + retention/cleanup | P1 | consistent deletion (object + index) |

### 4.6 Workflow (Execution + Nodes)
| Feature | Priority | Acceptance Criteria |
|---|---|---|
| workflow definition/versioning/publishing | P1 | version history is traceable |
| variable system (input/output/context) | P1 | correct mapping; correct scoping |
| execution control (run/pause/retry/replay) | P1 | failures diagnosable; retry works |
| node pluginization (see Section 6) | P1 | tenant-level install works |
| import/export (YAML/JSON) | P2 | reusable templates |


### 4.7 Core Execution Model (Run / Step / Artifact / Cost)
| Feature | Priority | Acceptance Criteria |
|---|---|---|
| Run lifecycle (create/update/status/timestamps) | P0 | run created for every execution; terminal status preserved |
| Step append-only logging (typed steps) | P0 | each LLM/tool/retrieval/node creates a step; steps are immutable |
| Artifact references (object storage-backed) | P0/P1 | DB stores refs only; upload/download via Storage gateway; tenant-scoped keys |
| Cost metering (normalized records) | P1 | cost records exist for LLM/tool/egress; attributable to run/step |
| Run history query + filters | P1 | searchable by tenant/workspace/time/status/type |
| Replay/retry semantics (workflow/agent) | P1/P2 | reruns create new steps; previous history preserved |


### 4.8 Observability
| Feature | Priority | Acceptance Criteria |
|---|---|---|
| end-to-end TraceId + RunId | P0 | every request has TraceId and creates a Run (run_id) |
| runtime logs (Workflow/Tool/LLM) | P0/P1 | filterable by trace/time |
| basic cost dashboard/report | P1 | token/cost can be aggregated |
| metrics & alerting (later) | P2/P3 | Prometheus/OTel optional |

### 4.9 Memory
| Feature | Priority | Acceptance Criteria |
|---|---|---|
| short-term memory (context window policy) | P2 | configurable window/cropping |
| long-term memory interface (vector + summaries) | P2 | pluggable store and retrieval |
| memory injection strategies | P2 | relevance controllable & observable |

### 4.10 Enterprise Security Boundary
| Feature | Priority | Acceptance Criteria |
|---|---|---|
| SSO (OIDC first) | P2 | integrates with enterprise IdP |
| audit logs (tamper-resistance direction) | P2 | key ops recorded |
| guardrails (rules/redaction/allow-deny lists) | P2 | policies configurable and verifiable |
| Vault/KMS adapters | P2 | secret lifecycle controlled |

---

## 5. Definition of Done (DoD) per Milestone

### M0 (P0) DoD
- [ ] Multi-tenant isolation (at least `tenant_id` end-to-end)
- [ ] Identity/RBAC enforced (API Key and/or JWT)
- [ ] LLM/Tools/Vector/Storage gateway interfaces finalized with minimal implementations
- [ ] Registry supports plugin registration + enable/disable (minimal lifecycle)
- [ ] Core execution model is enforced: Run + Step are always created; Artifacts are refs; Costs are recorded for metered boundaries
- [ ] SSE streaming protocol works (including error/interruption handling)
- [ ] Logs include TraceId and RunId and can be queried by them

### M1 (Chat) DoD
- [ ] Create session, send messages, paginate message history
- [ ] Streaming stable (proper client disconnect handling)
- [ ] `provider:model` routing works
- [ ] Basic token/cost records exist

### M3 (Dataset) DoD
- [ ] Upload → parse/chunk → embeddings → vector upsert
- [ ] Retrieval returns citation snippets + sources
- [ ] Deleting documents cleans both index and stored objects

### M5 (Workflow) DoD
- [ ] At least 5 node plugins available (LLM/Tool/If/SetVar/HTTP)
- [ ] Run history searchable; failure reasons diagnosable
- [ ] Variable mapping and context flow correct

---

## 6. Workflow Node Plugin List (Suggested Initial Set)

> Nodes are delivered as plugins with install/uninstall/upgrade. Inputs/outputs follow a unified schema.

### 6.1 Control Nodes
- Start / End
- Set Variable (write to context)
- If / Switch (branching)
- Merge (join branches)
- ForEach (iterate)
- Delay / Wait

### 6.2 LLM Nodes
- LLM Chat (text)
- LLM JSON (structured output validation)
- LLM Tool-Calling (tool invocation mode)

### 6.3 Tool & Integration Nodes
- HTTP Request (supports signing/secret injection)
- Webhook Trigger
- Tool Invoke (invoke installed tools via Tools Gateway)

### 6.4 Dataset Nodes
- Dataset Retrieve (vector retrieval)
- Rerank (optional)
- Compose Answer (compose response with citations)

### 6.5 Data Processing Nodes (Later)
- Text Transform (clean/truncate/template)
- JSON Transform (map/select/merge)
- Code Runner (Python/JS, later)

---

## 7. Implementation Constraints (Brief)

- **Stable Kernel:** Kernel contains only abstractions, protocols, execution, and observability. Concrete implementations live in adapters/plugins.
- **Protocol First:** Gateway/Plugin IO should be schema-driven to avoid implicit coupling.
- **Traceability:** Workflow/Agent/Tool/LLM all produce queryable run records (minimum: `trace_id`, `tenant_id`, `start/end`, `status`, `error`, `cost`).
- **Secure by Default:** secrets never land in logs; tool invocation permissions and quotas are controllable.

---

## 8. Suggested Repo Docs
- `DEVELOPMENT_PLAN.md` (this document)
- `ARCHITECTURE.md` (core architecture & principles)
- `PLUGIN_SPEC.md` (plugin protocol + manifest/schema)
- `WORKFLOW_DSL.md` (workflow DSL + variable conventions)
