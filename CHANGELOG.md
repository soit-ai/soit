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

- Gateway examples for curl, the OpenAI Python and Node SDKs, LangChain and
  the OpenAI Agents SDK (`examples/gateway/`), and a compatibility suite that
  drives the OpenAI Python SDK against `/v1` in CI (`server/tests/compat`):
  completions, streams, tool calls, structured output, base64 embeddings,
  model listing, image generation and edits, and error classes.
- Console: Settings › Notifications lists the workspace's team channels with
  the alerts each receives, and lets owners and admins add, test and delete
  them; other members are told who manages them. The budget row now switches
  the member's own budget and credit alerts (the `alert` category) instead of
  showing inert checkboxes, and a category a stored preference predates reads
  as on, as the server treats it.
- Console: Build › Models has a Virtual models tab that lists each
  `vmodel:` name with its targets in failover order, and creates, edits,
  disables and deletes them. Targets are picked from the model library or
  typed as a `model:` ref, and reordered in place; the slug callers use stays
  fixed.
- Console: Govern › Budgets lists every budget with its spend in the current
  period against the limit, its forecast, when it resets and what happens at
  the limit, flags the ones at risk, spent or on course to overrun, and
  creates, edits, disables and deletes them. A budget for one key, member,
  service principal or agent names it. `GET /api/v1/billing/budgets/statuses`
  returns every budget's status in one call.
- Console: Settings › API shows what bounds each key and edits its limits
  (calls per minute and per 24 hours, tokens per day, allowed addresses and
  models, and whether its runs record content), sets them when a key is
  created, and issues keys to service principals. The same page lists the
  workspace's service principals with their role, owner and active keys, and
  creates, disables and deletes them. Settings › Security switches the
  workspace between recording run content and metadata only.
- Runs report the entry they came through and the key that started them
  (`source`, `api_key_id`), and the run list (`GET /api/v1/runs`), its CSV
  export and every cost breakdown under `/api/v1/runs/costs` filter by both,
  so gateway traffic and its spend can be read on their own or per key. In
  the console, Observe › Runs has an Entry filter and a key filter that
  Settings › API links each key to, and the cost overview follows them. The
  Observe dashboard's recent runs include gateway embedding and image calls
  alongside chat.
- Workspace notification endpoints: team channels and webhooks that receive
  a workspace's alerts in the categories they subscribe to (`alert` for
  budgets and credit, `task` for failed runs), whoever is on the team
  (`/api/v1/notifications/workspace-endpoints`, workspace owners and admins,
  migration `20260927160000`). Budget thresholds now notify workspace owners
  and admins, and credit and budget alerts, like failed runs, reach members'
  own email and webhook endpoints as their delivery preferences allow instead
  of only the in-app inbox. The preference check and delivery staging are one
  shared step for every alert.
- Budgets: spending limits for a workspace, an API key, a user or service
  principal, or an agent, per UTC day or month, in one currency
  (`/api/v1/billing/budgets`, migration `20260927150000`). Spend is read from
  the daily aggregates for completed days and from the cost ledger for today,
  and `GET /api/v1/billing/budgets/{id}/status` reports spent, remaining,
  percent and a forecast to the end of the period. A hard-stop budget refuses
  model and tool calls once spent, with a 402 `BUDGET_EXHAUSTED` that names
  the budget, what it spent and when it resets, and writes the refusal to the
  audit ledger; admitted calls hold a short reservation of the average call
  cost, so concurrent callers overshoot a limit by about one call at most.
  Crossing a threshold (50, 80 and 100 percent by default) publishes one
  `billing.budget.threshold_reached` event per budget, period and threshold.
  Workspace owners and admins manage budgets. Tool calls now pass the same
  credit and budget checks as model calls.
- Daily usage aggregates. Runs record the entry they came through
  (`source`: `platform` or `gateway`) and the API key that started them, and
  a new `usage_daily_aggregates` table sums metered calls, tokens and priced
  amount per UTC day, source, user or service principal, key, provider, model
  and operation (migration `20260927140000`). A `cost.recorded` consumer adds
  each usage fact as it arrives, exactly once; a reconciler in the outbox
  dispatcher processes rebuilds each finished day from the cost ledger
  (`USAGE_RECONCILE_INTERVAL_SECONDS`), and the two never count a fact twice.
  Rehearsal runs are kept apart as source `rehearsal`. The run trace export
  carries `source` and `api_key_id`.
- Service principals: non-human callers of a workspace, such as a pipeline
  or a partner system, each with a human owner and a workspace role
  (`/api/v1/service-principals`, migration `20260927130000`). A workspace
  owner or admin creates them and issues them API keys (`principal_id` on
  `POST /api/v1/api-keys`). A key issued to a principal authenticates as the
  principal, so runs, costs and audit are attributed to it; it acts only in
  its own workspace, with the lower of its role and its owner's current role,
  and stops working when the principal is disabled or the owner leaves.
- Content-free runs. A workspace's `content_capture` can be `metadata_only`
  (`PATCH /api/v1/workspaces/{id}`), and an API key can ask for it on its own
  calls. Run and step summaries, output previews and error text are then
  stored as a length and a SHA-256 prefix instead of the text; statuses,
  error codes, tokens, costs and timings are recorded as before, and callers
  still get their answers. A key can tighten its workspace's mode but not
  loosen it, a workspace admin may switch a workspace to `metadata_only`, and
  only a tenant admin may switch it back. Work a worker starts on its own
  reads the workspace setting, and withholds content if it cannot. Migration
  `20260927120000` adds the columns; existing workspaces keep content.
- Virtual models: a workspace name, called as `vmodel:{slug}`, for an
  ordered list of up to eight `model:` refs
  (`/api/v1/modelhub/virtual-models`, migration `20260927110000`). A call
  tries the targets in turn: an unavailable target (disabled, removed, or
  missing a capability the call needs) is skipped, and a call that fails with
  a timeout, 408, 409, 429, a 5xx or a lost connection moves to the next
  target once that target's own retries are spent. An invalid request or a
  policy refusal is not repeated elsewhere, a stream moves on only before its
  first chunk, and an image call is never repeated on another provider
  because the failed one may have been billed. Each attempt is recorded on
  the run step, and cost is attributed to the provider that answered.
  `/v1/models` lists active virtual models, and an API key's model list can
  name them.
- API keys carry their own limits: model calls per minute, calls per 24
  hours, tokens per UTC day, an IP allowlist and the model refs they may
  call. They apply on top of the member's own limits, and a null means no
  limit of that kind. The key's owner or a workspace admin sets them when the
  key is created or with `PATCH /api/v1/api-keys/{key_id}`, and rotation keeps
  them. A call over a rate or quota answers 429 with `Retry-After`; a call
  from another address or to another model answers 403, and `/v1/models`
  lists only the models the key may call. `TRUSTED_PROXIES` names the proxies
  whose `X-Forwarded-For` is believed, so an allowlist sees the real client
  rather than an address the client wrote. Migration `20260927100000` adds
  the columns; existing keys keep working unchanged.
- An OpenAI-compatible gateway under `/v1`: `POST /v1/chat/completions`
  (whole or streamed, with tools, images and structured output),
  `GET /v1/models`, `POST /v1/embeddings`, `POST /v1/images/generations` and
  `POST /v1/images/edits` (multipart; the mask's transparent pixels mark the
  region to edit, as in OpenAI's API, and are converted to SOIT's
  white-is-edit convention). Image sizes outside 64-4096 pixels are refused
  before the call is billed.
  An OpenAI SDK pointed at SOIT with a SOIT API key works unchanged. Every
  call is a governed run (`mode=gateway`, subject the API key or the user)
  that passes the same rate limits, quotas, credit checks, content safety and
  cost recording as SOIT's own agents, and the run id comes back in the
  `x-soit-run-id` header. A refusal before a stream starts answers with its
  own status code, a failure mid-stream ends the stream with an OpenAI error
  event, and a stream the client abandons fails its run with
  `CLIENT_DISCONNECTED`. `/v1/models` lists the workspace's active models by
  the ref a call names. Only `n=1` is accepted, so each choice stays one
  governed call.
- Anthropic models call tools natively. The adapter refused any request with
  tools; it now offers them under provider-safe names, sends assistant tool
  calls as `tool_use` blocks and tool results as `tool_result` blocks (merging
  consecutive turns so roles alternate), translates `tool_choice`
  (`auto`, `required`, `none` or a named tool), and streams tool input as
  `input_json_delta` fragments assembled into complete calls. The Anthropic
  capability preset now reports `tools`. Tool-name aliasing moved to one
  module shared with the OpenAI adapter.
- Chat messages can show images beside their text (`ChatMessage.images`, by
  URL or `data:` URL). The OpenAI Chat Completions, OpenAI Responses and
  LiteLLM adapters send them as image parts and the Anthropic adapter as image
  blocks; content safety still inspects the text and keeps the images when it
  rewrites it, and context-window trimming keeps them too.
- The OpenAI adapter sends `response_format`, `stop` and `seed` to Chat
  Completions, and a forced tool choice names the tool by the alias it was
  offered under. On the Responses API (official GPT-5.5 models) structured
  output travels as `text.format` and a forced tool choice in Responses form;
  `stop` is refused there because Responses cannot honour it, and a seed,
  best effort in Chat Completions, is not sent.

### Fixed

- Work started with an API key can be stored and resumed. Durable
  interactions (the Responses API, agent and workflow streams) store the
  caller's context in a JSON column, and a context authenticated by an API
  key carries the key's scopes as a set, which could not be encoded: every
  such request failed with a server error. Contexts are now written and read
  back through one JSON form, and fields a newer release adds are ignored by
  an older worker during a rollout.
- Streamed chat is inspected by content safety like a whole reply. The
  prompt was sent to the model uninspected and the streamed text reached the
  client unchecked, so a credential in either direction passed through. The
  prompt is now inspected before the stream opens, and the output is released
  a sentence at a time after inspection: a redaction replaces the text before
  the client sees it, and a refusal ends the stream. Findings are recorded on
  the run step as they are for a whole reply.
- A streamed Anthropic call reports its prompt tokens. The stream's
  `message_start` usage was ignored, so streamed calls recorded zero input
  tokens and were priced on output alone. Prompt-cache writes and reads now
  count as input on both the streamed and the whole-reply path.
- Rate limiters share one Redis connection pool per event loop. The policy
  gateways are built per request, and each opened a pool of its own for its
  limit checks that was never closed, so a busy API held sockets for every
  recent model call.
- Local file storage uses the absolute root in `STORAGE_URL` on Linux and
  macOS. The root lost its leading slash and was resolved under the process
  working directory, so `file:///data/storage` became `./data/storage`: the
  lite profile's API never turned ready because it could not create that
  directory, and the default development store nested itself under the
  server directory. Files an earlier version wrote there must be moved to the
  configured root.

### Changed

- An API key is accepted as `Authorization: Bearer sk_...` as well as in
  `X-API-Key`, which is how OpenAI SDKs and most HTTP clients send one. The
  request context records which key authenticated a call, for per-key limits
  and attribution, and a key's `last_used_at` is written at most once a
  minute instead of on every request.
- A call refused by a rate limit or a daily quota answers 429 with a
  `Retry-After` header and the code `RATE_LIMIT_EXCEEDED`; it was a 403
  `FORBIDDEN`, which clients could not tell apart from a permission refusal
  and so never retried.
- Routes under `/v1` answer errors in the OpenAI shape
  (`{"error": {"message", "type", "param", "code"}}`) and without the SOIT
  envelope, ready for the OpenAI-compatible entry point. Routes under
  `/api/v1` are unchanged.

## [1.1.0] - 2026-09-26

### Added

- A lite profile, `docker/docker-compose.lite.yml`, runs every feature in
  five long-running containers with no `.env`: PostgreSQL with pgvector,
  Redis, the API (which also runs the chat interaction worker), the web UI,
  and one worker that runs knowledge ingest, the outbox dispatcher and the
  scheduler (`scripts/combined_worker.py`). Files live on a local volume, and
  a new `SECRETS_BACKEND=sealed` keeps secret values in PostgreSQL sealed with
  a key derived from `SECRET_KEY`, so they survive restarts without Vault
  (migration `20260926110000` adds the table). It is an evaluation profile:
  the settings refuse pgvector and sealed secrets in production. The README
  quick start leads with it, and CI starts it and runs `docker/lite-smoke.sh`,
  which stores a secret, restarts the API and checks the secret still
  resolves.

- The quickstart Compose stack is split into `docker/docker-compose.infra.yml`
  (PostgreSQL, Redis, MinIO, Milvus, Vault) and `docker/docker-compose.app.yml`
  (migrations, API, web and workers), so an operator who already runs some of
  that infrastructure starts only what is missing. `docker/docker-compose.yml`
  includes both and keeps the `soit` project name, volumes and commands, so an
  existing quickstart is unaffected. Docker Compose v2.24 or later is required,
  as the optional `env_file` entries already did.
- `migrate` waits up to `DATABASE_WAIT_SECONDS` (default 60) for the database
  to accept connections before running Alembic, and reports a database that
  never answers in one line.

- The durable chat interaction worker can run as its own process
  (`scripts/response_interaction_worker.py`, the `response-worker` service in
  the production compose file). One claim loop feeds up to
  `RESPONSE_INTERACTION_WORKER_CONCURRENCY` executions; the API only enqueues
  and tails when `RESPONSE_INTERACTION_WORKER_IN_API=false`.
- Worker metrics for capacity decisions: `soit_interaction_queue_wait_seconds`,
  `soit_interactions_in_flight`, `soit_interaction_execution_seconds` and
  `soit_interaction_claims_total`.
- `scripts/load_baseline.py --mode worker` measures the production shape
  (claim, worker execution, SSE tail) and reports queue wait.
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
- Two-factor authentication, by TOTP. `/me/mfa/setup` starts enrolment,
  `/me/mfa/confirm` activates it once a code proves the authenticator holds the
  secret, and returns ten single-use recovery codes. Once active, a password no
  longer signs in on its own: `POST /login` answers with a short-lived challenge
  and `POST /login/mfa` completes it. The challenge token authorizes nothing
  else. Turning it off requires the password.
- A workspace can require a second factor (`require_mfa`). Members without one
  are refused access to that workspace with a distinguishable reason, so they
  can be sent to enrol rather than shown an error they cannot act on.
- Workspace member listings report `mfa_enabled`.
- Schedules. A workspace can run an agent or a workflow on a cron expression,
  in a stated time zone, through `/api/v1/schedules`. Firing hands the work to
  the same durable path the API uses, so a scheduled run is an ordinary run —
  same ledger, same evidence, same recovery — and carries the schedule that
  started it. An expression that cannot fire is refused on save, and the
  endpoint can preview the next few firings before anything is stored.
- A missed occurrence is skipped by default: a scheduler down for a day would
  otherwise wake and fire twenty-four hourly jobs at once. `catch_up` opts a
  schedule into running late, one occurrence per pass.
- `SCHEDULE_WORKER_ENABLED` runs the scheduler. It ships as its own container
  in both compose profiles, for the reason the outbox dispatcher does; several
  replicas may run it, and the claim ensures each occurrence fires once.
- The instance can send its own mail (`SYSTEM_MAIL_ENABLED`,
  `SYSTEM_MAIL_URL`), which unlocks three flows that previously had nothing
  behind them. `GET /auth/capabilities` reports whether it can, so the console
  offers a reset or an email invitation only where one would actually arrive.
- Password reset: `POST /auth/password-reset` mails a single-use link that
  expires in 30 minutes, and `POST /auth/password-reset/confirm` sets the new
  password and ends every other session. The request answers the same way for
  an unknown address, so the form cannot be used to find out who has an
  account, and asking again retires the earlier link.
- Members can be invited by email address rather than by user id:
  `/workspaces/{id}/invitations`. An invitation names one address and is
  refused for anyone else, so a forwarded link cannot move the membership.
  Withdrawing one stops its link immediately.
- Address confirmation: `POST /me/email-verification` mails a link, and
  `/auth/email-verification/confirm` records when it was confirmed.
- A failed run now reaches the notification centre, not just Observe. It goes
  to the members who can act on it, respects the recipient's category
  preference, and stays quiet for rehearsal runs.
- An account can be closed on request. `/me/deletion-request` records the ask
  with a withdrawal period (`ACCOUNT_DELETION_GRACE_DAYS`, default 7); closing
  ends sessions, revokes API keys, drops the second factor and deactivates the
  user. Runs, audits and approvals are untouched — they record who authorised
  what. The last owner of a tenant is refused: ownership has to be handed over
  first. `ACCOUNT_DELETION_SWEEPER_ENABLED` closes due requests without an
  operator clicking, and is on in the production profile.
- Governance policy is versioned. Every save of a workspace's or tenant's
  egress rules and usage limits appends a revision carrying the whole policy,
  `GET /security/policies/revisions` reads that history,
  `/security/policies/revisions/diff` reports what one save changed, and
  `/security/policies/revisions/{id}/rollback` puts an earlier one back by
  appending it rather than rewinding the record.
- A policy has a stable identifier derived from its content, read from
  `GET /security/policies/bundle` and shown in the console. Identical rules
  always produce the same identifier and reordering a rule list produces no new
  one, so it can be cited. Outbound requests the policy refuses now record the
  tenant and workspace identifiers they were refused by, so a refusal stays
  readable after the rules have moved on.
- A tool call that stops for approval is now recorded, not only raised. The
  request is written to the governance ledger before the run suspends, so a
  task waiting for a decision can be opened, read and answered by somebody who
  was not watching the stream it was raised on, and the decision that closed it
  is recorded against the call it belongs to. Rehearsal runs never queue a
  person for a decision.
- An agent draft carries a review state and the time it has been waiting.
  `POST /agents/{id}/versions/{version_id}/review` sends a draft for review or
  answers one, and `GET /agents/drafts/awaiting-review` lists what the
  workspace is waiting on, oldest wait first. It is a state on the draft, not a
  review ticket: what a team needs first is to tell work in progress apart from
  work waiting on somebody.
- The audit ledger can be asked a question. `GET /runs/audits` takes
  `actor_user_id`, `resource_type`, `resource_id` and `outcome` alongside the
  existing window, entries now carry who acted and what they touched rather
  than only the gateway and the run, and the console's audit log filters on
  those instead of eyeballing one page. The entry count reports what matched
  the filters, not how many rows fit on the page.
- Content safety ships with a provider instead of only a port. A deterministic
  in-process rule provider inspects what goes to a model and what comes back
  for credentials (private keys, cloud and provider tokens, JWTs) and for
  personal identifiers (email, phone, card numbers validated by checksum,
  national ids). Credentials are redacted by default because a key in a prompt
  is never wanted; personal data is recorded rather than rewritten, because
  silently altering real work is worse than reporting it. Findings go into run
  evidence, never the matched text. `CONTENT_SAFETY_PROVIDER=http` still sends
  content to a classifier a deployment operates, which remains the only way to
  judge tone, intent or confidentiality.
- Three regression sets ship instead of one, covering grounded answering,
  ticket operations and the full customer-support path, and the deterministic
  runner takes each case's expected answer from the case rather than knowing
  it. A suite that covers one scenario is a demo.
- The agent publish tab shows the last ten runs of the release gate: pass rate,
  what regressed against the baseline, what was fixed, and whether the gate
  blocked. An agent with no report says so rather than showing an empty chart.
- The Agents workbench review tab reads the drafts the workspace is waiting on
  and answers them in place, instead of showing a fixture. The console now
  reports its own version on the About pane, stamped at build time.
- `MILVUS_MODE=lite` runs the vector store as embedded Milvus Lite against a
  local file, so knowledge and retrieval can be debugged without the Milvus,
  etcd and MinIO containers. It is a development switch: one process owns the
  file, the index is `FLAT` rather than `IVF_FLAT`, there is no Windows build,
  and production startup refuses it.
- `VECTOR_BACKEND=pgvector` keeps each collection as a table in PostgreSQL, so
  local development can reuse the database it already runs instead of standing
  up Milvus. Scores match Milvus for the same metric; the index is HNSW, and
  vectors wider than 2000 dimensions go unindexed because pgvector will not
  index them. Production startup requires the `milvus` backend.
- `POST /images/edits` edits an existing image under a text instruction, in the
  three shapes that are one provider call: inpainting (image and mask),
  outpainting (a pre-expanded canvas whose new margin is masked), and reference
  editing (image, no mask). It runs the same governance chain as generation —
  one rate limit, one daily quota, one credit check, one trace step, one cost
  row — and appears in the ledger as `edit_image`, so an edit is told apart from
  a generation without a second mechanism existing.
- The mask convention is fixed at the API boundary and published with every
  response as `mask_convention`. White marks the region to edit. The two
  conventions in use are exact opposites, and guessing wrong does not degrade an
  edit, it inverts it: adapters convert per provider so one mask means one thing
  on every route.
- Image models can declare what they will actually accept — `mask`,
  `transparent_background`, `max_dimension`, `supports_seed` — and a request
  against a trait the model has ruled out is refused with one SOIT error code
  before the provider is called and before anything is billed. Only declared
  traits are enforced; a model that never stated one is routed as before.
- Image generation and editing accept `async=true`, returning a run id
  immediately and finishing the work in the background, and
  `response_format=artifact`, writing results into governed run storage. Four
  2048px images are 10-16 MB of base64 in one response body, which a gateway
  cuts before the provider has finished.
- Generated and edited images are inspected by the content safety port before
  they are stored or returned, so a refused image never becomes a durable
  artifact. A deployment whose classifier reads only text records that fact
  rather than an all-clear: the evidence distinguishes "inspected and clean"
  from "never inspected".

### Changed

- An agent turn loads its conversation branch from the head down to a
  window (`THREAD_HISTORY_MAX_MESSAGES`, default 200; a request's
  `context_window_messages` or a thread's `max_history_messages` narrows
  it) instead of listing the whole ledger twice. On an 800-turn thread a
  turn dropped from about 245 ms to about 105 ms; conversations longer
  than the window keep their newest messages in context.
- The backend runs on Python 3.12 (`requires-python` admits 3.11 and 3.12;
  the image, CI and `.python-version` use 3.12).
- The web console requires Node.js 22.22 or later, the floor React Router
  8 declares; CI, `web/.nvmrc` and the web image all run Node 24.
- New knowledge bases default to `workspace` visibility, and migration
  `20260926100000` sets every existing `private` knowledge base to
  `workspace`, which keeps the access members had while visibility was not
  enforced. Mark a knowledge base `private` to limit it.
- JSON columns and API responses are encoded with orjson; log records are
  written from a listener thread (`LOG_ASYNC=false` restores synchronous
  writes).
- The Redis event bus publishes keyed events on `<channel>:<key>` in addition
  to the base channel, so a process only receives the conversations it tails.
  Anything subscribed to the base channel still sees every event.
- A worker learns of new work from an `interaction.claimed` bus event instead
  of waiting out `RESPONSE_INTERACTION_WORKER_POLL_INTERVAL`; polling stays as
  the fallback.
- Agent response verification is now opt-in. The verifier is a second model
  call on every turn, so a published version that wants it sets
  `policies.verify: true` (or a caller passes `verify: true`); versions
  that do not say answer with one call. Previously every turn was verified
  unless the version turned it off.
- Image cost snapshots record the shape of the request — `size`, `quality`,
  `steps` — alongside the count. The rate is still per image; without the shape
  the images column could not explain itself, because four 4096px images and
  four 256px images bill identically.
- Model capability refusals answer 4xx instead of 500. A model that cannot serve
  the requested capability is a fact about the request, not a server fault.
- License documentation clarified: the usage-condition wording previously
  stated in the README (multi-tenant hosting, frontend branding) was
  removed; SOIT Community is licensed under the Apache License 2.0.
- The web container image moved from Node 20 to the Node 24 LTS line.
- Authentication failures from context resolution now carry their code and
  details instead of being flattened to a bare message, because some refusals
  name something the client must do about them.
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

- The `local-embedding` extra moves to torch 2.13.0 and torchvision 0.28.0,
  past the torch advisories that affect every release up to 2.12.1, and
  drops the torchaudio pin nothing imports. The pin was also what held torch
  at 2.6.0: it stopped Dependabot's security update from resolving.
- The quickstart API runs the durable interaction worker
  (`RESPONSE_INTERACTION_WORKER_ENABLED=true`). Without it, queued
  interactions such as task retries and approval resumes were accepted and
  never executed.
- Testing a secret fails when its value is missing from the store. Stores
  that cannot find a value answer with an empty string, which the test used
  to report as a successful resolution.
- Deciding an agent run's approvals anywhere other than the chat (the
  approvals page, the task page, the API) now finishes the run. The approval
  consumer used to mark the task running and stop there, so a run whose chat
  client had gone away stayed running forever. Once every approval the run
  waits on is decided, the consumer queues a resume that carries the
  decisions for the durable interaction worker, on the same run, task and
  response; a rejection resumes it too, and the agent records the refused
  tool call and finishes its turn. A checkpoint a chat client is already
  resuming is left to that client.
- Knowledge visibility is enforced. A `private` knowledge base is reachable
  only by its creator, workspace owners and admins, and members holding a
  resource grant on it: listings, the knowledge workbench, global search and
  the agent builder's knowledge catalog leave it out for everyone else, and
  reading, querying or editing it directly returns 403. The field was stored
  but never checked, so every member could reach every knowledge base. Only
  the creator or a workspace owner or admin can change a knowledge base's
  visibility, and the retrieval summary now checks access like every other
  knowledge route.
- Creating a knowledge base with the console's second visibility choice
  failed: it sent `restricted`, a value the API rejects. The choices are now
  `workspace` and `private`, and the settings page can change visibility.
- A workflow version's `spec.limits` are enforced: `timeout_ms` bounds the
  run's wall clock and cancels the node in flight, `max_steps` caps the nodes
  started, `budget` stops the run once its recorded cost in
  `budget_currency` reaches the budget, and `max_tool_calls` caps tool calls.
  The limits were compiled into the plan but never read. A stopped run fails
  with the limit as its error code (`time_budget_exceeded`, `max_steps`,
  `cost_budget_exceeded`, `tool_budget_exceeded`), matching the agent loop.
- Concurrent credit deductions for one workspace book serially under a
  PostgreSQL advisory lock that grants share, so a threshold crossed by two
  overlapping deductions publishes exactly one low or exhausted alert instead
  of two or none. PostgreSQL contracts cover redelivery, repeated pricing of
  one cost entry, parallel sums and threshold races, and the credit API now
  has entrypoint tests for owner-only grants.
- On a PostgreSQL server whose default time zone is not UTC (a Windows
  installer picks the machine's zone), every timestamp the API wrote landed
  shifted by that offset, because psycopg renders aware datetimes in the
  session zone before a `timestamp without time zone` column drops it. The
  engine now pins each connection to UTC. Rows written before the fix on such a
  server keep their shifted values.
- The console read offset-less API timestamps as the browser's local time, so
  every time and "ago" label was off by the viewer's UTC offset. Timestamps are
  now marked as UTC where the response envelope is unwrapped.
- Settings › Billing showed `undefined` after every figure and an empty credit
  ledger: it expected a currency, a `consumed_total` and a paginated list, and
  the API returns unitless credits, a signed `deducted_total` and a bare list.
- The Overview's run count and pass rate were computed from one page of runs,
  which the API caps at 100, so a busy workspace reported "100 in the last
  24h". Both tiles now read the window summary. Governance audits in the feed
  are labelled by their operation and time of record, and an `allow` outcome no
  longer renders as a failure; the side panel and the audit log's block list
  had the same labels.
- The Knowledge "Web crawl" and "Git sync" filters never matched a library,
  because documents record their source as `crawler` and `git`.
- The Plugins table showed "—" for risk and scopes although the API returns
  both; it now shows the derived risk level and the declarations behind it.
- The Workflows tiles said "7d" while counting runs since midnight UTC; they
  now say "today".
- The console prototype seed failed on current schemas (provider slug, tool
  call control records) and on a second workspace (teammate emails). It now
  also seeds the operational history the console reads — schedules, task
  timelines, decided approvals, notifications, grants, policy revisions,
  ingest queues, draft reviews, releases, dead letters, workflow and knowledge
  runs, regression reports and run artifacts — so every list, state and tile
  has data (`scripts/seed_console_operations.py`).
- The production Compose file probed the API's readiness at
  `/api/v1/health/ready`, a path that does not exist, so the `api` container
  stayed `unhealthy` for its whole life. It now probes `/health/ready`, with a
  5-second request timeout that fits inside the healthcheck's own 10 seconds.
  The Quality Gate and database-connection docs quoted the same wrong path.
- Image calls to any `gpt-image` model failed at the provider with
  `Unknown parameter: 'response_format'`. The models always answer with inline
  base64 and reject the parameter that asks for it, while LiteLLM still lists it
  as supported. This affected generation, which shipped earlier, as well as the
  new edit endpoint. A request that asks for `url` from such a model is now told
  so plainly rather than quietly handed base64.
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
- Replaying a regression set against an agent version called tools for real. A
  rehearsal now answers tool calls at the boundary instead of making them, so
  testing a release no longer files tickets, pages people or spends money on
  third parties; the run is marked as a rehearsal so cost and dashboards can
  leave it out.
- Uploading a document to a knowledge base with no index was accepted with a
  201 and then failed in the background, where nobody was watching. The upload
  is now refused up front, saying an index has to exist first.

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

[Unreleased]: https://github.com/soit-ai/soit/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/soit-ai/soit/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/soit-ai/soit/releases/tag/v1.0.0
