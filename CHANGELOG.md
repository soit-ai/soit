# Changelog

All notable changes to SOIT Community are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Release notes with database compatibility ranges, upgrade guidance, and release
evidence requirements live under [`docs/releases/`](./docs/releases/). Entries
here are a user-facing summary; per-release notes remain the authoritative
record for operators.

## [Unreleased]

Everything below is targeted at the `v1.0.0` Community release. When the release
tag is created, this section moves under a `## [1.0.0]` heading with the release
date, and a fresh `[Unreleased]` section is started.

### Added

**Agent runtime**

- Agent build, publish, and execute path with versioned capability bindings.
- Native function-calling agent loop with planner and verifier, replacing
  prompt-based JSON parsing.
- Streaming agent execution over SSE, converged onto the durable interaction
  path so streams survive client disconnects.
- Automatic RAG retrieval from attached knowledge bases during agent runs.
- Stateful agent runtime contract with snapshot-based retry: failed
  non-streaming runs can be retried by replaying their interaction snapshot.
- Agent regression baselines: historical runs can be promoted to regression
  cases, and publish can replay active cases before writing a release.

**Workflow engine**

- Visual workflow builder with canonical node schemas, scoped builder
  resources, and a frozen capability baseline.
- Workflow publish, execute, monitor, retry, and replay with full run linkage.
- Checkpoint-based resume for interrupted workflow runs.
- Execution detached from the originating HTTP request, with orphan-run
  reclamation (`SKIP LOCKED`) and a unified dead-letter view across every
  execution kind.

**Knowledge**

- Document upload, parsing (PDF, Word, Markdown, plain text), chunking with
  multiple strategies, indexing, query, and citation path.
- Lease-based knowledge ingest workers with orphan-task recovery; a worker
  that loses its lease can no longer perform terminal writes.

**ModelHub**

- Model provider setup, diagnostics, and authoritative runtime routing
  (LiteLLM as the core routing dependency).
- Governed image generation end to end.
- Configurable fallback call timeout.

**Chat**

- Conversation management (create, update, list, paginated history) and chat
  completion with message persistence and tracing.

**Plugins, tools, and MCP**

- Plugin-first governance: MCP server and Skill artifacts are installed and
  governed through the Plugin module.
- MCP tool adapter and registry routing for invoking tools on remote MCP
  servers, with OAuth 2.1 authorization for protected servers.
- Package trust chain enforced in production, with revocation support and a
  satisfiable strict integrity profile.
- Capability registry API.

**Governance and observability**

- Runtime ledger covering run detail, steps, tool calls, costs, citations,
  child runs, and audit evidence, inspectable through run replay and the
  Audit Explorer.
- Tracing for streaming, embedding, and rerank LLM calls.
- Evaluation module: LLM-as-judge case scoring, recorded human verdicts, and
  trend reporting.
- Pluggable content safety and PII port.
- Event outbox architecture with background dispatcher, idempotent consumer
  checkpoints, and dead-letter tables, backing run/task/workflow lifecycle
  events and observability projections.

**Billing and cost**

- Priced usage recorded as one row per invocation with dedicated dimension
  columns and `billing_basis` semantics enforced by database invariants.
- Credit deduction ledger derived from priced usage, with balance enforcement
  (warning and hard stop) and low-balance alerts delivered to admin inboxes
  via the outbox.

**Identity and access**

- User, workspace, and tenant management with workspace-scoped resources.
- Scoped, expiring API keys instead of inherited full access; key scopes are
  carried through request-context rebuilds and cap ownership and grants.
- Guardrail changes separated from agent development permissions.

**Deployment and release engineering**

- Docker-based self-hosted topology (`server`, `knowledge-worker`, `web`)
  with a hardened production profile and verifiable guardrails.
- Tag-triggered release pipeline publishing digest-addressable images,
  SPDX SBOMs, Sigstore build provenance and SBOM attestations, a
  deterministic source archive, and `SHA256SUMS`.
- Release verification scripts for artifacts, fresh-install and N-1
  migration acceptance, and the governance demo.
- End-to-end live-stack test suites for chat, workflow streaming, responses,
  and ingestion, plus a concurrency and latency baseline script.
- `/health/ready` reports vector store status.

### Changed

- Backend restructured into the kernel / modules / adapters / api layering
  with import-linter enforcement.
- Agent streaming, response interactions, and knowledge ingest converged onto
  a shared lease-based execution path.
- Usage and charge records consolidated into single priced-usage rows;
  `entry_type` retired from `run_cost_entries`.
- `plugin_refs` deprecated and merged into `tool_refs`.
- Explicit N-1 database schema baseline frozen; migrations aligned with
  acceptance contracts.
- Observe, Task, Run Explorer, and API settings surfaces moved off hardcoded
  Chinese copy onto the i18n system, with English (`en-US`) as the default
  locale and matching `zh-CN` translations; server-generated observability
  labels are now English.
- The CJK date-format option was removed from language and region settings;
  `YYYY-MM-DD` covers the same field order. Workspaces still holding the retired
  value fall back to an unselected date format until one is chosen.

### Fixed

- Milvus connections are established lazily and mocked cleanly in tests;
  dashboard aggregation tolerates NULL cost amounts.
- Workflow builder exposes only supported nodes and serializes canonical
  contracts; settings and test-run behavior aligned.
- Orphaned workflow runs are claimed before being failed.
- Retry is no longer offered for tasks that could never run.
- One-shot init containers are verified by completion instead of health.
- Home dashboard shows a clear error banner on load failure.

### Security

- All outbound application paths governed by egress policy.
- Secrets referenced through scoped, opaque secret IDs; controlled secret
  injection for plugin-owned tools.
- Grant revocation is cache-safe; empty capability bindings fail closed.
- Internal exception detail no longer leaks into error responses.
- `/metrics` gated; user name length bounded; self-signup can be disabled.
- Production startup refuses the object storage credentials shipped in
  `.env.example` and MinIO's own stock defaults, closing the gap where the
  production compose file required `STORAGE_OPTIONS_JSON` to be set but not to
  differ from the development value.

[Unreleased]: https://github.com/soit-ai/soit/commits/main
