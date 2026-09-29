# Minimal Topology

The quickstart command names twelve services. A demo on a small machine does
not need all of them. This page says what each container is for, which ones a
scenario can leave out, and what stops working when it does. It is derived from
the Compose files in `docker/` and from the readiness gate in
`server/app/api/v1/health/router.py`; if the two disagree, the code wins.

None of the reduced shapes below is a supported production deployment. The
production settings validation (`validate_runtime_requirements` in
`server/app/settings/settings.py`) refuses to start without Milvus, the Redis
event bus, Vault and the dedicated outbox dispatcher, so the distance between
the demo shape and the production shape is exactly the list of services this
page removes. The background of this page is a post on the project site,
[I tried to cut our twelve-container stack down to four](https://soit.ai/en/blog/minimal-topology).

## What each service does

| Service | Defined in | Role | What depends on it |
| --- | --- | --- | --- |
| `postgres` | `docker-compose.infra.yml` | The ledger: business data, runs, steps, tool calls, audit events and the outbox. | Everything. A hard readiness gate: `/health/ready` answers `503` without it. |
| `redis` | `docker-compose.infra.yml` | Event bus between processes (`EVENT_BUS_BACKEND=redis`), permission cache, rate limiter, usage counters and budget reservations. | Every application service waits for it. |
| `minio` and `minio-init` | `docker-compose.infra.yml` | Object storage for uploads, artifacts and knowledge documents. `minio-init` is a one-shot job that creates the bucket and exits. | Everything. A hard readiness gate, like PostgreSQL. |
| `etcd` | `docker-compose.infra.yml` | The metadata store of Milvus itself, not a dependency of SOIT. | `milvus` only. |
| `milvus` | `docker-compose.infra.yml` | Vector store for knowledge retrieval. | Knowledge bases. Readiness reports it but does not gate on it. |
| `vault` | `docker-compose.infra.yml` | Secret values, in dev mode (values are lost when the container restarts). | Secrets, unless `SECRETS_BACKEND=sealed` (below). |
| `migrate` | `docker-compose.app.yml` | One-shot job: waits for PostgreSQL, applies the Alembic migrations, exits. | `api` and the workers start only after it succeeds. |
| `bootstrap` | `docker-compose.app.yml` | One-shot job: creates the admin user, tenant and workspace, exits. | The first sign-in. |
| `api` | `docker-compose.app.yml` | The API, the OpenAI-compatible `/v1`, the MCP endpoint and the web UI's backend. It also hosts the chat interaction worker and the reapers. | Everything. |
| `web` | `docker-compose.app.yml` | The console. | The UI. |
| `knowledge-ingest-worker` | `docker-compose.app.yml` | Chunks and embeds uploaded documents. | Knowledge ingestion. |
| `outbox-dispatcher` | `docker-compose.app.yml` | Delivers events committed to the outbox to their consumers. | Usage aggregates, budget thresholds, notifications, task retries and observe counters (details below). |
| `scheduler` | `docker-compose.app.yml` | Fires due schedules. Not part of the quickstart command. | Cron schedules. |

`/health/ready` names the hard requirements: the database and the object
storage answer `503` when unreachable, while the vector store is probed for at
most two seconds and reported as `"vector": "unavailable"` without lowering
readiness. Redis is not probed, but every application service waits for it and
the event bus is configured to use it, so treat it as required in the full
files.

## Topology 1: the lite profile

The smallest install that runs every feature, and the right answer for most
demos:

```bash
docker compose -f docker/docker-compose.lite.yml up -d
```

Five resident containers (`postgres` with pgvector, `redis`, `api`, `web`,
`worker`) plus the one-shot `storage-init`, `migrate` and `bootstrap` jobs, and
no `.env`. Compared with the full files: vectors live in PostgreSQL through
pgvector instead of Milvus and etcd, files on a local volume instead of MinIO,
secret values sealed in PostgreSQL with a key derived from `SECRET_KEY` instead
of Vault, and one `worker` runs knowledge ingest, the outbox dispatcher and the
scheduler together.

Nothing stops working. The trade is durability and scale: changing
`SECRET_KEY` orphans the sealed secret values, and the settings refuse pgvector
and sealed secrets when `ENVIRONMENT=production`. See
[docker/README.md](../docker/README.md#lite-profile).

## Topology 2: the full files without vector retrieval

For a demo of chat, agents, tools, MCP servers, workflows, the gateway and the
governance features, with no knowledge base. Start the bundled infrastructure
you still need, then the application, from the two files separately:

```bash
cp .env.example .env
docker compose --env-file .env -f docker/docker-compose.infra.yml up -d --wait postgres redis minio minio-init vault
docker compose --env-file .env -f docker/docker-compose.app.yml up -d migrate bootstrap api web outbox-dispatcher
```

Seven resident containers (`postgres`, `redis`, `minio`, `vault`, `api`,
`web`, `outbox-dispatcher`) plus the one-shot `minio-init`, `migrate` and
`bootstrap` jobs. Both files use the project name `soit`, so the application
finds the infrastructure by service name.

Use the two files, not `docker/docker-compose.yml` with a shorter service
list: the quickstart entry point layers `docker-compose.deps.yml` over the
application, which makes `api` depend on `milvus` being healthy, so
`up -d api` on that file starts Milvus and etcd whether they are named or not.

What stops working:

- Knowledge bases: creating one, uploading documents, retrieval, the knowledge
  retrieval node in workflows and agents bound to a knowledge base all fail,
  because `MILVUS_HOST=milvus` does not resolve. `/health/ready` still answers
  `200` with `"vector": "unavailable"`.
- Document ingestion, since `knowledge-ingest-worker` is not started either.
- Schedules, since `scheduler` is not started (the quickstart does not start it
  either).

pgvector is not an option for the full files: the bundled `postgres:15` image
does not ship the `vector` extension. A demo that needs knowledge retrieval
without Milvus is what the lite profile is for.

### Variant: without Vault as well

Add `SECRETS_BACKEND=sealed` to `.env` and drop `vault` from the first
command:

```bash
docker compose --env-file .env -f docker/docker-compose.infra.yml up -d --wait postgres redis minio minio-init
docker compose --env-file .env -f docker/docker-compose.app.yml up -d migrate bootstrap api web outbox-dispatcher
```

Secret values are then sealed in PostgreSQL with a key derived from
`SECRET_KEY`, as in the lite profile, with the same conditions: changing
`SECRET_KEY` orphans them, and the setting is refused when
`ENVIRONMENT=production`. Six resident containers.

## Leaving a worker out

The three workers are separate processes of the same image, and each can be
left out on its own:

| Left out | What still works | What stops |
| --- | --- | --- |
| `knowledge-ingest-worker` | Everything else, including existing knowledge bases. | Newly uploaded documents stay queued and are never chunked or embedded, so they never become searchable. They are picked up when the worker starts. |
| `outbox-dispatcher` | Runs execute and are recorded: chat, agent and workflow execution schedule their steps in-process, not through the outbox. | The outbox consumers: daily usage aggregates, budget thresholds and their alerts, credit deduction, notifications for failed runs and budgets, re-driving retried tasks, and the observe counters and trace metrics. Events stay pending in the outbox and are delivered once the dispatcher runs. |
| `scheduler` | Everything else. | Schedules never fire. A missed occurrence is skipped unless the schedule asks to catch up. |

`OUTBOX_DISPATCHER_ENABLED` is fixed to `false` in the application file, so
the dispatcher cannot be folded into the `api` container of the full files
through `.env`; the lite profile's `worker` is where all three loops run in
one container.

## What the full files cannot drop

- `postgres` and `minio`: readiness gates. MinIO also carries every upload the
  API and the workers exchange; the application services of the full files
  share no file volume, so `STORAGE_URL=file://...` would give each container
  its own private store. The lite profile mounts a shared volume for that.
- `redis`: every application service waits for it, and the event bus, rate
  limiter and permission cache are configured to use it.
- `migrate` and `bootstrap`: `api` starts only after both exit successfully.

## Checking a reduced stack

```bash
docker compose --env-file .env -f docker/docker-compose.app.yml ps
curl http://localhost:9200/health/ready
```

Expected: `api` healthy, `web` healthy, the one-shot jobs `Exited (0)`, and a
readiness body of `{"status":"ready","database":"connected","storage":"connected","vector":"connected"}`,
with `"vector":"unavailable"` when Milvus is not part of the stack. Then open
`http://localhost:5000` and sign in as the bootstrap admin
(`admin@example.com` / `changeme123` unless overridden in `.env`).

Related pages: the [quickstart](quickstart.md) for the full topology,
[troubleshooting.md](troubleshooting.md) when a service does not come up, and
[Use Infrastructure You Already Run](../docker/README.md#use-infrastructure-you-already-run)
for pointing the application at services you operate yourself.
