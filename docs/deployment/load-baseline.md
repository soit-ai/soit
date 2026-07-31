# Load and Failure-Injection Baseline

**No baseline figures are published in this repository, because none have been
measured.** This document is the procedure for producing them. Numbers from
someone else's hardware would be worse than none: they would be quoted in
capacity plans that do not hold.

Record results in a private evidence file, not here. Throughput and latency
depend on the model provider, the vector store, node concurrency and the host,
so a figure is only meaningful alongside the environment that produced it.

## Prerequisites

Run against the hardened profile, not the development compose. The development
stack runs Vault in dev mode, bundles every dependency on one host, and lets
execution happen inside the request; none of that predicts production
behaviour.

```bash
docker compose -f docker/docker-compose.production.yml up -d
```

Use the deterministic `model:test:*` provider path for repeatability. Measuring
against a live model measures the provider, not SOIT.

## What to measure

| Metric | Source | Why |
|---|---|---|
| Concurrent runs sustained | `soit_active_runs` | The number the runtime holds without the backlog growing |
| Run duration P50/P95/P99 | `soit_run_duration_seconds` | Tail latency, not the average |
| Run failure ratio | `soit_runs_total{status="failed"}` | Whether load degrades correctness or only speed |
| Outbox oldest pending age | `soit_outbox_oldest_pending_age_seconds` | Whether the dispatcher keeps up |
| Outbox dead letters | `soit_outbox_dead_letters` | Load must not produce terminal failures |
| Recovery time | Wall clock | From fault injection to the queue draining again |

Report the load level each figure was taken at. A P95 without the concurrency
it was measured under is not a baseline.

## Failure injection

Each scenario has an expected behaviour the runtime already implements. The
drill checks that the implementation holds under load, and produces the
recovery-time figure.

| Scenario | Command | Expected |
|---|---|---|
| API killed mid-execution | `docker compose -f docker/docker-compose.production.yml kill -s KILL api` | Workflow runs whose lease lapses are marked `failed` with `WORKFLOW_EXECUTION_ORPHANED` by the reaper; interactions are reclaimed by a worker after their lease expires |
| Dispatcher killed | `... kill -s KILL outbox-dispatcher` | Pending outbox events accumulate, then drain when it restarts; none are lost |
| Ingest worker killed | `... kill -s KILL knowledge-ingest-worker` | The in-flight task's lease expires and another worker reclaims it |
| Database briefly unreachable | Block the port with the host firewall | Requests fail; no run is left reporting `running` once leases lapse |
| Model provider timeout | Point the provider at an unroutable address | Runs fail with a provider error and cost is still attributed |

After each: confirm no execution is left in a non-terminal state once every
lease has expired, and record how long the queue took to drain.

The orphan sweep interval is `WORKFLOW_ORPHAN_REAPER_INTERVAL` (30s default)
and the workflow lease is `WORKFLOW_EXECUTION_LEASE_SECONDS` (120s default), so
expect recovery on the order of the lease plus one sweep, not instantly.

## Evidence to retain

- Environment: host spec, replica counts, database and vector store sizing
- Load generator, its configuration, and the duration of each run
- The metric values above, with the load level for each
- One record per injection scenario: command, observed behaviour, recovery time
- Any execution found stuck in a non-terminal state — that is a defect, not a
  measurement

## Status

Not yet executed. Until it is, SOIT publishes no capacity or latency claims.
