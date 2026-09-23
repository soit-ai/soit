# Database connection budget

Every SOIT process opens its own PostgreSQL connection pool. Since the runtime
moved to an async engine there is no thread pool between requests and the
database: one API worker can hold up to `DATABASE_POOL_SIZE +
DATABASE_MAX_OVERFLOW` connections at once, and so can each worker process.

## Who holds connections

| Process | Count in `docker-compose.production.yml` | Max connections each |
|---|---:|---:|
| `api` (uvicorn `--workers ${API_WORKERS:-4}`) | 4 | pool + overflow |
| `response-worker` | 1 | pool + overflow |
| `outbox-dispatcher` | 1 | pool + overflow |
| `ingest-worker` | 1 | pool + overflow |
| `schedule-worker` | 1 | pool + overflow |
| `migrate` (short-lived) | 1 | a handful |

With the defaults (`DATABASE_POOL_SIZE=10`, `DATABASE_MAX_OVERFLOW=20`) that is
`8 x 30 = 240` connections at full load, before superuser reserves, backups and
ad-hoc sessions. PostgreSQL's own default `max_connections` is 100.

## The response worker's in-flight bound

`response-worker` executes `RESPONSE_INTERACTION_WORKER_CONCURRENCY`
interactions at once. An execution gives its connection back while it waits
on the model, but every other phase needs one, and so do the claim loop and
each lease heartbeat, so the worker caps that setting at
`DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW - 4` and logs a warning when the
setting is higher. Measured on an 8-core host with the default 30-connection
pool, 24 in flight is the knee for one process; 64 in flight on the same pool
starved the heartbeats and was slower. For more capacity run more replicas of
`response-worker` and count each one in the formula below.

## Rule of thumb

```
max_connections >= processes x (DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW) + 20
```

Pick one side and derive the other:

- **Managed database with a fixed ceiling** (the production compose expects an
  external `DATABASE_URL`): set `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW`
  so the formula holds. With `max_connections=100` and eight processes, use
  `DATABASE_POOL_SIZE=5` and `DATABASE_MAX_OVERFLOW=5`.
- **Self-hosted PostgreSQL**: raise `max_connections` instead. The development
  compose file starts PostgreSQL with `-c max_connections=200`
  (`POSTGRES_MAX_CONNECTIONS` overrides it), which covers the defaults with
  headroom. Above ~300 connections put PgBouncer in transaction-pooling mode in
  front of the database rather than raising the ceiling further.

`API_WORKERS` is the other knob: the async runtime is CPU-bound per process at
roughly 80 ms of Python per agent execution, so 2-4 workers per container is
the useful range, and each one adds a full pool to the budget above.

## What the formula is, and is not

The formula above is an upper bound: it is what the processes *may* hold, not
what they normally do. Each pool grows lazily, so a worker only opens as many
connections as it has concurrent in-flight requests.

Measured on the load ladder (4 API workers, 50 concurrent agent executions, one
box): **40 established connections**, against an upper bound of
`4 x (10 + 20) = 120`. Size `max_connections` against the bound, because a
latency spike is exactly when every pool fills at once; but do not read a
shortfall against the bound as an immediate outage.

## Symptoms of an undersized budget

- `FATAL: sorry, too many clients already` in the API or worker logs;
- requests that hang for `pool_timeout` (30 s) and then fail with
  `QueuePool limit ... reached`;
- the readiness probe (`/health/ready`) flapping under load while the
  database itself is idle.
