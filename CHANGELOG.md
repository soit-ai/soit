# Changelog

All notable changes to SOIT Community are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Release notes with database compatibility ranges, upgrade guidance, and release
evidence requirements live under [`docs/releases/`](./docs/releases/). Entries
here are a user-facing summary; per-release notes remain the authoritative
record for operators.

## [Unreleased]

### Added

- List endpoints can report how many rows match the filters, not just the page
  they returned. `with_total=true` on runs, run steps, run audits and tasks adds
  a `total` to the response. It is opt-in because the count costs a query, and
  its absence means the count was not requested rather than that nothing
  matched.
- Run audits and tasks accept a `since`/`until` creation window, so a caller can
  ask for "the last 24 hours" instead of paging through history. Runs, run steps
  and cost summaries keep their existing `started_after`/`started_before`.
- `GET /runs/summary/window` reports what a workspace did inside one window:
  run volume, outcome counts, pass rate and money spent, all counted rather than
  derived from a page of runs. The pass rate is absent until something settles,
  because zero would read as "everything failed".
- The run cost summary now carries `charges` — amounts by currency under the
  same filters — so "what did this agent cost today" is one question instead of
  two that can disagree.
- The task workbench summary reports queue depth and how long the oldest
  waiting task has waited.
- Outbound requests the egress policy refuses are now recorded in the audit
  ledger, and `GET /security/egress/blocks` reports them for a window with the
  refusals behind the count. This is distinct from `/security/egress/audits`,
  which records changes to the policy rather than the requests it stopped.
- Resolving a secret is recorded in the audit ledger — that it happened, never
  what it resolved to — and `GET /secrets/resolutions/summary` counts those
  resolutions for a window.
- `GET /runs/tools/invocations` counts governed tool invocations per tool from
  the cost ledger, busiest first.
- `GET /knowledge/{id}/retrieval/summary` reports retrieval quality for a
  window — hit rate against a stated score threshold, and how many queries
  returned nothing. It reads the retrieval steps each query already writes, so
  no query text is stored to produce it.
- Plugin responses carry a `risk_level` with the declared scopes behind it, and
  `update_available` when an installation is pinned behind the published
  version. Both are derived from what the plugin declares and what is
  installed, so neither can drift from the record it describes.
- `GET /resource-grants` can be asked for a whole workspace: `resource_type` and
  `resource_id` are optional, and omitting the id lists every grant in scope.
  The access surface previously had to fan out one request per object.
- Sign-ins are now sessions a person can see and end. `GET /me/sessions` lists
  them with device, address and last activity; `DELETE /me/sessions/{id}` ends
  one and `POST /me/sessions/revoke-all` ends the rest. Access tokens name their
  session, so ending one stops its token immediately rather than whenever the
  token happens to expire.
- `POST /refresh` exchanges a refresh token for a new access token. Refresh
  tokens rotate on every use, and presenting a spent one is treated as a replay:
  the session ends. The console renews silently, so an expiry mid-session is no
  longer something the user sees.
- Workspace member listings report `last_active_at`, derived from the member's
  own sessions.
- `GET /me/workspaces` lists the workspaces the caller belongs to, so a
  workspace can be switched without signing out. Listing every workspace in a
  tenant stays an administrative question needing admin rights.
- Saved views and pinned objects are stored per user, per workspace:
  `/me/views` and `/me/pins`. Saving a view over an existing name replaces it,
  and only one view per screen can be the default.

### Changed

- License documentation clarified: the usage-condition wording previously
  stated in the README (multi-tenant hosting, frontend branding) was
  removed; SOIT Community is licensed under the Apache License 2.0.
- The web container image moved from Node 20 to the Node 24 LTS line.
- `ACCESS_TOKEN_EXPIRE_MINUTES` drops from 480 to 30. It is no longer the
  session length — clients renew against `/refresh` — so it now means the worst
  case delay before a revoked session stops working. `REFRESH_TOKEN_EXPIRE_DAYS`
  (default 14) is the session length.
- Python runtime dependencies refreshed across the lockfile (42 packages,
  minor/patch), verified by the full backend suite, pip-audit, ruff, and
  pyright.
- Console theme reworked onto the SOIT brand palette: the primary colour is
  now Signal Blue with Governance Teal as the contrast accent, in both light
  and dark mode.
- Chart series colours no longer reuse green, amber, or red, so a chart is
  never mistaken for a status readout.
- Informational badges moved to a neutral slate so they stay distinguishable
  from the blue brand affordances.
- Console feature views moved off the default Tailwind palette onto design
  tokens, so status, identity, and brand colours are now consistent across
  every screen.
- Workflow node types, model providers, knowledge types, and metric tiles use a
  dedicated categorical palette instead of borrowing status hues.
- The auxiliary accent moved from teal onto the quiet end of the blue ramp,
  because teal sat close enough to success green to be confusable on span lines
  and status dots.

### Fixed

- Dark-mode success, warning, and info badges rendered near-black text on a
  dark tint of their own hue, leaving the label unreadable.
- The prompt-versus-completion token bar drew a breakdown in success green,
  which read as a pass rather than a share of a total.
- A relationship-graph label was drawn in a near-white cyan on a light panel,
  leaving it effectively invisible.
- `POST /responses` executed on a hardcoded default model when the caller named
  an agent but no model, instead of the model that agent's published version
  binds. A workspace that has no route to that default saw the call fail.
- The deterministic in-process model provider registered for non-production
  builds could not be reached: canonical `model:test:*` references were
  rejected for having no workspace route, which no in-process provider can
  have.
- The page canvas stayed light under a dark console. The console's theme class
  is scoped to its own container, and the document element was still owned by
  the pre-rebuild provider, which defaulted to light. The console shell fills
  the viewport and hid it; the sign-in and sign-up screens scroll, so a light
  band showed around them. Native scrollbars and form controls now follow the
  theme as well.

## [1.0.0] - 2026-08-05

The first public release of SOIT Community. Release notes with database
compatibility and known limitations: [docs/releases/v1.0.0.md](./docs/releases/v1.0.0.md).

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

- The project remains Apache-2.0 licensed, with additional usage conditions
  stated in the README: operating a multi-tenant service requires a
  commercial license from SOIT LLC, and the frontend LOGO and copyright
  notice may not be removed or modified.
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

- Every published host port in the quickstart Docker topology is now
  overridable through `*_PUBLISHED_PORT` variables, and the documented
  quickstart command passes `--env-file .env` so those overrides actually
  reach compose interpolation; previously redis, milvus, vault, api, and web
  ports were hardcoded and collided with existing local services.
- The web lockfile is regenerated with cross-platform optional dependencies,
  fixing the Docker web image build (`npm ci`) from a lockfile produced on
  Windows.
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
- The server, knowledge-worker, and web container images now run as
  dedicated non-root users, and the web build context excludes local env
  files.
- React Router upgraded to 8.3.0, clearing GHSA-qwww-vcr4-c8h2 (RSC-mode
  CSRF bypass; SOIT does not use the affected RSC APIs) from the dependency
  audit, and `cryptography` upgraded to 50.0.0, clearing PYSEC-2026-3552.
- Production startup refuses the object storage credentials shipped in
  `.env.example` and MinIO's own stock defaults, closing the gap where the
  production compose file required `STORAGE_OPTIONS_JSON` to be set but not to
  differ from the development value.

[Unreleased]: https://github.com/soit-ai/soit/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/soit-ai/soit/releases/tag/v1.0.0
