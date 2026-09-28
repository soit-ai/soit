# The runtime ledger: contract, exports and evidence bundles

Everything SOIT runs is recorded in its ledger: runs, run steps, cost
entries, audit events and outbox events. This page describes the shape in
which that record leaves SOIT, and the two ways to take it out.

## The contract

`server/app/kernel/specs/v1/ledger_spec.schema.json` (JSON Schema 2020-12)
defines five record types. Every exported record is wrapped in an envelope
that names the contract version it was written in:

```json
{"schema_version": "1.0", "record_type": "cost", "record": {"cost_entry_id": "ce_…", "amount": "0.0012", "currency": "USD", "created_at": "2026-09-27T10:30:15.123456Z", "…": "…"}}
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
  images it asked for (`requested_images`) at its route's per-image price.
  The provider may still make and bill every one. Before the provider is
  asked, the step records that number, the model asked for and the target
  and provider serving it (`requested_images`, `model`, `model_ref` and the
  `provider_*` fields in its metrics), so the charge can be told even
  without the process. A call refused or answered with an error before the
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
