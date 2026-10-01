# The runtime ledger: contract, exports and evidence bundles

Everything SOIT runs is recorded in its ledger: runs, run steps, cost
entries, audit events and outbox events. This page describes the shape in
which that record leaves SOIT, and the two ways to take it out.

## The contract

`server/app/kernel/specs/v1/ledger_spec.schema.json` (JSON Schema 2020-12)
defines five record types. Every exported record is wrapped in an envelope
that names the contract version it was written in:

```json
{"schema_version": "1.1", "record_type": "cost", "record": {"cost_entry_id": "ce_…", "amount": "0.0012", "currency": "USD", "created_at": "2026-09-27T10:30:15.123456Z", "…": "…"}}
```

| `record_type` | Source | Key fields |
| ------------- | ------ | ---------- |
| `run` | `runs` | `run_id`, `mode`, `kind`, `status`, `source`, `api_key_id`, subject, timings, error |
| `step` | `run_steps` | `step_record_id`, `run_id`, `step_type`, `status`, `metrics`, error |
| `cost` | `run_cost_entries` | `cost_entry_id`, `amount`, `currency`, tokens, provider, model, tool |
| `audit` | `audit_events` | `audit_id`, `event_type`, `operation`, `outcome`, actor, resource, `payload` |
| `event` | `event_outbox` | `event_id`, `event_type`, subject and correlation ids, `payload` |

Conventions: timestamps are UTC with a `Z` suffix; amounts and quantities are
decimal strings, so no reader rounds them; structured fields stay objects.
Outbox delivery state (leases, attempts, last error) stays inside SOIT.

Versioning: adding an optional field is a minor version (`1.1`); removing,
renaming or retyping one is a major version. A contract test fails whenever a
ledger table gains a column the contract does not account for, so every
change to what leaves the runtime is a reviewed change.

## Image prices

A model's `pricing_json` prices images per image. `image` is the plain rate;
`image_variants` lists prices for a `quality`, a `size` or both, for
providers whose price depends on them:

```json
{
  "currency": "USD",
  "image": "0.042",
  "image_variants": [
    {"quality": "low", "price": "0.011"},
    {"quality": "high", "price": "0.167"},
    {"quality": "high", "size": "1536x1024", "price": "0.25"}
  ]
}
```

A call is priced by the variant that fits it, that is whose every named
value equals the call's; of several, the one naming more values wins, and
of equals the first listed. The cost row's `pricing_snapshot` names the
variant (`image_variant`) and records the call's `size` and `quality` under
`quantities`. A call no variant fits takes `image`; without an `image` rate
it is recorded unpriced with the reason `image_variant_not_priced` rather
than billed at another quality's price. A call that asks for no quality, or
for `auto`, is priced as one that names none.

## Charges SOIT estimates

Most cost rows record what the provider reported. Two kinds of call are
charged an estimate instead, because the provider was asked and its full
answer never came, and neither kind is cancelled at the provider by SOIT
giving up. Both are flagged `usage_estimated` on the step's metrics and in
the cost row's `pricing_snapshot`; the snapshot's `usage_estimate_basis` says
what the estimate counts:

- A streamed model call that ends without the provider's usage (the client
  left, the stream failed part way, or the backend never sends usage) is
  charged tokens estimated from the prompt and the text generated
  (`characters`); see [the gateway's streams](gateway.md#streams).
- An image call that times out after the provider was asked, or that was in
  flight when the process making it was lost, is charged the number of
  images it asked for (`requested_images`) at its route's per-image price
  for the size and quality it asked for. The provider may still make and
  bill every one. Before the provider is asked, the step records that
  number, the size and quality when given, the model asked for and the
  target and provider serving it (`requested_images`, `image_size`,
  `image_quality`, `model`, `model_ref` and the `provider_*` fields in its
  metrics), so the charge can be told even without the process. A call refused or answered with an error before the
  timeout is not charged.

An image job lost with its process, after a restart or a crash, is failed with
`IMAGE_JOB_INTERRUPTED` by the image job reaper. The reaper is off unless
`IMAGE_JOB_REAPER_ENABLED` is set; the shipped compose files and
`.env.example` set it. An image call in progress, asynchronous or not, marks
its run alive every `IMAGE_JOB_HEARTBEAT_SECONDS` (30 by default); a run left
unmarked for `IMAGE_JOB_ORPHAN_AFTER_SECONDS` (600, and never less than three
heartbeats) counts as lost. A model call it left in flight is charged as
above, at the price its route has when the reaper runs, and the cost row is
dated then, not when the call was made. If the route no longer resolves the
charge is recorded unpriced, with `reason` `route_not_resolved` in its
snapshot and the provider named from the step. A job lost before it asked the
provider is not charged.

The first sweep after an upgrade also fails image runs that earlier versions
left open. Their steps predate the record of what was asked, so they are
closed without a charge. During a rolling upgrade, a replica still on an
earlier version sends no heartbeat, so an image job it runs for longer than
`IMAGE_JOB_ORPHAN_AFTER_SECONDS` can be failed while it is still waiting on
the provider; enable the reaper once every replica is upgraded. Heartbeats
and the cutoff are stamped by each replica's own clock, so keep replica
clocks in sync: skew eats into the margin.

## Checking costs against a bill

Every metered call leaves one cost row, so the ledger can be read the way a
provider's bill is: per key, per principal, per model or tool, per day. Each
row has a pricing status:

| Status | Meaning |
| --- | --- |
| `priced` | An amount computed from what the provider reported. |
| `estimated` | An amount computed from usage SOIT estimated (`usage_estimated`, see above). |
| `free` | An explicit price of zero. |
| `unpriced` | No amount: no price applied. `unpriced_reason` says why, such as `pricing_not_configured`, `image_variant_not_priced` or `tool_pricing_not_declared`. |

An unpriced row is never counted as zero, and amounts in different currencies
are never added together.

```
GET /api/v1/runs/costs/entries?since=…&until=…&api_key_id=…&pricing_status=unpriced
GET /api/v1/runs/costs/reconciliation?since=…&until=…&group_by=model
```

- Both take the same filters: the run's `api_key_id`, `user_id` (a member or
  a service principal) and `source` (`platform` or `gateway`), and the row's
  `model_ref`, `provider_slug`, `tool_ref`, `source_port`, `operation`,
  `currency` and `pricing_status`.
- `/costs/entries` lists rows oldest first, each with its run's
  `api_key_id`, `user_id` and `run_source`, its `pricing_status` and, when
  unpriced, its `unpriced_reason`. Its `until` is inclusive, as before.
- `/costs/reconciliation` covers the half-open window `[since, until)`, like
  the exports. It answers the priced total per currency (`amounts`), the part
  of it computed from estimated usage (`estimated_amounts`), the rows per
  status (`status_counts`) and the unpriced rows per reason
  (`unpriced_reasons`). With `group_by` (`model`, `provider`, `tool`,
  `api_key`, `user`, `source`, `operation` or `day`) it adds one row per
  value and currency, with unpriced rows in a row of their own; at most 500
  rows, and `groups_truncated` says when there were more.
- Rows are dated when they were written. A charge the image job reaper
  records for a lost call is dated when the reaper ran, so it can fall in a
  later window than the call.
- `external_reconciliation` is `not_performed`: this is the ledger's side of
  the check only.
- Model calls keep the provider's own ids on their rows, when it gave them:
  `upstream_id`, the response's id (`chatcmpl-…`, `msg_…`, Gemini's
  `responseId`), and `upstream_request_id`, the request id from its response
  headers (`x-request-id`, `request-id`). Both filter `/costs/entries`, so a
  line of a provider's request log finds its row. Neither is unique:
  self-hosted servers and caching proxies repeat ids. An id an SDK made up is
  not kept (LiteLLM's own `chatcmpl-<uuid>`, and any id for Anthropic through
  LiteLLM, where only the request id survives). Embeddings and images have a
  request id at most; charges for unanswered image calls, rows written before
  1.6 and tool calls have neither. Providers' usage exports are mostly per
  hour or day, so most bills are still matched by model, key and time window.
- Workspace readers can call both, as they can the other `/runs/costs`
  reads.

In the console, Observe › Costs shows the reconciliation for a window, with
the grouping and filters above, and **Export CSV** downloads the grouped rows.

## Exports

```
GET /api/v1/exports/{runs|steps|costs|audit|events}?since=…&until=…&format=jsonl|csv
```

- One kind of record created in `[since, until)`, oldest first, for the
  caller's workspace. `until` defaults to now; a window covers at most 92
  days.
- `jsonl`: one envelope per line. `csv`: the contract's fields as columns, in
  contract order, with objects as JSON cells. The contract version is in the
  `X-SOIT-Ledger-Schema` response header.
- Streamed in keyset batches, so a large window is never held in memory.
- Workspace owners and admins only. Each export is itself written to the
  audit ledger as `ledger.exported`, with the window and format.
- The audit export covers every audit event of the workspace, in a run or
  not: gateway requests, egress and budget refusals, policy changes, exports.

In the console, **Export** on Observe › Runs and Govern › Audit downloads
the current window as CSV.

## Run evidence bundles

```
GET /api/v1/runs/{run_id}/evidence
```

One run's evidence as a zip a reviewer can take away and check without SOIT:

| File | Holds |
| ---- | ----- |
| `run.json`, `steps.jsonl`, `costs.jsonl`, `audit.jsonl` | ledger records in the contract |
| `tool_calls.jsonl` | the run's tool calls |
| `approvals.jsonl` | approval requests and decisions |
| `citations.jsonl` | knowledge citations |
| `content_safety.jsonl` | content safety findings per step (categories and decisions, never the matched text) |
| `policy.json` | the policy bundle ids the run's decisions were made under |
| `governance.json` | the governance evidence matrix of the run detail |
| `manifest.json` | versions, content capture mode, child runs, and each file's SHA-256, size and record count |
| `SHA256SUMS` | every file's digest, for `sha256sum -c` |

The bundle keeps no more content than the workspace records: under
`metadata_only` capture, run and step summaries and error text, step
metrics, audit payloads, tool arguments, results and metadata, approval
details, citation text and the URLs in governance evidence are withheld,
rows recorded before the workspace went content-free included. A context
that cannot tell the workspace's mode withholds content.

The archive is deterministic: an unchanged run always gives the same bytes,
so the digest in `X-SOIT-Evidence-SHA256` identifies the evidence. Each
download is written to the audit ledger as `run.evidence_exported` with that
digest, but not attached to the run, so downloading does not change the
evidence. **Evidence bundle** on a run's detail page downloads it.

## Trace export (OTLP)

```
GET /api/v1/runs/trace/{trace_id}/otlp
```

A trace, the runs sharing a `trace_id` and their steps, as an OTLP/JSON
`ExportTraceServiceRequest` (`application/json`, downloaded as
`trace-<id>.otlp.json`) that an OpenTelemetry collector, Jaeger or Tempo
accepts on its OTLP/HTTP endpoint:

- One resource (`service.name: soit`, `soit.tenant.id`, `soit.workspace.id`,
  `soit.trace.id`) and one scope named `soit`.
- One span per run, named `run <kind>`, whose parent is the parent run's
  span when that run is in the trace, and one span per step, named by its
  step type, under its run's span. A run without a parent is a `SERVER`
  span, a model, tool or retrieval step a `CLIENT` span, everything else
  `INTERNAL`.
- The trace id is the stored id when it already is 32 hex characters, and
  otherwise a 16-byte BLAKE2b hash of it; a span id is an 8-byte BLAKE2b
  hash of the run or step id. An unchanged trace always gives the same
  document.
- `startTimeUnixNano` and `endTimeUnixNano` come from the record's
  timestamps, as decimal strings; a run or step still open ends where it
  started.
- `status.code` is `OK` (1) for `succeeded`, `ERROR` (2) with the error code
  as the message for `failed`, and `UNSET` (0) otherwise.
- Attributes: `soit.run.*` (id, mode, kind, status, subject, attempt, parent
  and source run, source, sandbox, error code), `soit.step.*` (id, step id,
  type, node id, status, error code) and each numeric top-level step metric
  as `soit.step.metric.<name>`.

The document holds identifiers, enumerations, timings and numbers only:
summaries, error text, tool arguments and results are never in it, so a
content-free workspace exports the same shape. The contract is
`kernel/specs/v1/otlp_trace_spec`. Each download is written to the audit
ledger as `trace.otlp_exported` with the run and span counts. A trace with
no run in the caller's workspace is `404`. **Export OTLP** on a trace's
page downloads it.
