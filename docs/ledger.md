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
`metadata_only` capture, tool arguments and results, approval details and
citation text are replaced by a length and a hash. A context that cannot
tell the workspace's mode withholds content.

The archive is deterministic: an unchanged run always gives the same bytes,
so the digest in `X-SOIT-Evidence-SHA256` identifies the evidence. Each
download is written to the audit ledger as `run.evidence_exported` with that
digest, but not attached to the run, so downloading does not change the
evidence. **Evidence bundle** on a run's detail page downloads it.
