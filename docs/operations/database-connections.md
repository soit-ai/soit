# Database connection budget

Every SOIT process opens its own PostgreSQL connection pool. Since the runtime
moved to an async engine there is no thread pool between requests and the
database: one API worker can hold up to `DATABASE_POOL_SIZE +
DATABASE_MAX_OVERFLOW` connections at once, and so can each worker process.

## Who holds connections

| Process | Count in `docker-compose.production.yml` | Max connections each |
|---|---:|---:|
| `api` (uvicorn `--workers ${API_WORKERS:-4}`) | 4 | pool + overflow |
| `outbox-dispatcher` | 1 | pool + overflow |
| `ingest-worker` | 1 | pool + overflow |
| `schedule-worker` | 1 | pool + overflow |
| `migrate` (short-lived) | 1 | a handful |

With the defaults (`DATABASE_POOL_SIZE=10`, `DATABASE_MAX_OVERFLOW=20`) that is
`7 x 30 = 210` connections at full load, before superuser reserves, backups and
ad-hoc sessions. PostgreSQL's own default `max_connections` is 100.

## Rule of thumb

```
max_connections >= processes x (DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW) + 20
```

Pick one side and derive the other:

- **Managed database with a fixed ceiling** (the production compose expects an
  external `DATABASE_URL`): set `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW`
  so the formula holds. With `max_connections=100` and seven processes, use
  `DATABASE_POOL_SIZE=5` and `DATABASE_MAX_OVERFLOW=5`.
- **Self-hosted PostgreSQL**: raise `max_connections` instead. The development
  compose file starts PostgreSQL with `-c max_connections=200`
  (`POSTGRES_MAX_CONNECTIONS` overrides it), which covers the defaults with
  headroom. Above ~300 connections put PgBouncer in transaction-pooling mode in
  front of the database rather than raising the ceiling further.

`API_WORKERS` is the other knob: the async runtime is CPU-bound per process at
roughly 80 ms of Python per agent execution, so 2-4 workers per container is
the useful range, and each one adds a full pool to the budget above.

## Symptoms of an undersized budget

- `FATAL: sorry, too many clients already` in the API or worker logs;
- requests that hang for `pool_timeout` (30 s) and then fail with
  `QueuePool limit ... reached`;
- the readiness probe (`/api/v1/health/ready`) flapping under load while the
  database itself is idle.
