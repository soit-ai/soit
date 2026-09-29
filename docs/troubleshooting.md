# Troubleshooting the Quickstart

What the quickstart stack looks like when it does not come up, what each
health check is actually testing, and where to look. Everything here is
derived from the health checks and start-up ordering in
`docker/docker-compose.infra.yml` and `docker/docker-compose.app.yml`, and
from the one-shot scripts they run.

Three commands answer most questions. Run them from the repository root, with
the same `--env-file` and `-f` arguments as the `up` command:

```bash
docker compose --env-file .env -f docker/docker-compose.yml ps -a
docker compose --env-file .env -f docker/docker-compose.yml logs --tail 100 <service>
docker inspect --format '{{json .State.Health.Log}}' $(docker compose --env-file .env -f docker/docker-compose.yml ps -q <service>)
```

`ps -a` includes the one-shot jobs that have already exited; `ps` alone hides
them. The `inspect` command prints the last health-check attempts with their
output, which is where a failing probe explains itself. For the lite profile,
use `-f docker/docker-compose.lite.yml` and no `--env-file`.

## Symptom, cause, fix

| Symptom | Cause | Fix |
| --- | --- | --- |
| Services use the default ports, credentials or admin account although `.env` says otherwise; `migrate` fails with `password authentication failed` after you changed `DATABASE_PASS`. | `.env` did not reach Compose interpolation. The Compose files live in `docker/`, so Compose does not find the repository-root `.env` on its own. The application containers still read it through `env_file`, which is why the API sees your password while the bundled `postgres` was created with the default. | Always pass `--env-file .env` to every `docker compose` command, including `ps`, `logs` and `down`. |
| `Bind for 0.0.0.0:8200 failed: port is already allocated`, or on Docker Desktop `ports are not available: ... 0.0.0.0:5000`. | Another process on the host owns a default port. Vault's `8200` is taken by a local Vault, `5432` by a local PostgreSQL, `5000` by another web server (on macOS, the AirPlay receiver). | Override the host side only, in `.env`, with the matching `*_PUBLISHED_PORT` variable; the table is in [quickstart.md](quickstart.md#published-ports). After changing `API_PUBLISHED_PORT`, rebuild the web image with `VITE_BASE_URL`. |
| `milvus` sits in `Created` or `Waiting`; `api` and `knowledge-ingest-worker` never start. | `milvus` starts only after `etcd` and `minio` report healthy, and `api` waits for `milvus`. Whichever of `etcd` or `minio` is not healthy holds the chain. | `docker compose ... ps etcd minio`, then `logs` of the one that is not `healthy`. |
| `milvus` is `unhealthy` although `etcd` and `minio` are healthy. | Its probe, `curl -f http://localhost:9091/healthz`, gets 20 s of start period and then 10 attempts 15 s apart, so Milvus has about three minutes to come up. A slow disk, too little memory, or object-storage credentials that differ from MinIO's (`MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` are passed to both) keep it from getting there. | `docker compose ... logs milvus`. Check that the MinIO variables in `.env` are the same ones `minio` started with (see the volume note below). |
| `api` is `unhealthy`; `web` stays in `Created`. | The API probe requests `/health/ready`, which answers `503` when the database or the object storage is unreachable. `web` starts only once `api` is healthy. | `curl -i http://localhost:9200/health/ready`. `Database is unavailable`: check `postgres` and `migrate`. `Object storage is unavailable`: check that `minio-init` exited `0` (it creates the bucket) and that `STORAGE_OPTIONS_JSON` names reachable credentials. |
| `api` restarts or exits right after start. | The process failed before it could listen: a migration that did not run, or in `ENVIRONMENT=production` a setting the runtime validation refuses (pgvector, sealed secrets, in-process dispatcher, missing plugin signing keys). | `docker compose ... logs api`; the first traceback names the setting or the table. |
| `minio-init` stays `Up` for minutes and `api` never starts. | Its script loops on `mc alias set` until MinIO accepts the credentials, and `api` waits for it to complete. It never completes when `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` do not match what `minio` runs with. | `docker compose ... logs minio-init`. Align the variables, or reset the volume if MinIO was initialised with different ones. |
| `migrate` exited with a non-zero code; nothing after it starts. | `api`, the workers and `bootstrap` all wait for `migrate` to complete successfully. Its log says why it did not: `database ... did not accept connections within 60s` (PostgreSQL not reachable in `DATABASE_WAIT_SECONDS`), an authentication error (credentials differ from the ones the volume was created with), or an Alembic error. | `docker compose ... logs migrate`. For Alembic errors on an existing database, see the [migration runbook](release-migration.md). |
| `bootstrap` exited with a non-zero code. | The admin user could not be created: `BOOTSTRAP_ADMIN_PASSWORD` shorter than 8 characters, or the database rejected the write. `User already exists. Skipping bootstrap.` with exit code `0` is normal on every start after the first. | `docker compose ... logs bootstrap`. |
| The UI loads but every request fails, or sign-in hangs. | The browser calls the API at the address the web image was built with, `http://localhost:9200/api/v1` by default. It cannot follow a changed `API_PUBLISHED_PORT` or a remote host. | Rebuild the web image with `VITE_BASE_URL=http://<host>:<port>/api/v1`; the released `web` image only knows the default. |
| `outbox-dispatcher` is `unhealthy`. | Its probe fetches `http://localhost:9201/metrics`, which the process serves once it has validated its settings and loaded the plugin runtimes. A setting the production validation refuses, or a plugin that fails to load, stops it before that. | `docker compose ... logs outbox-dispatcher`. |
| Secrets stored yesterday are gone. | The bundled Vault runs in dev mode and keeps everything in memory; a restart of the `vault` container empties it. | Expected for the quickstart. The lite profile's sealed store, or a Vault you operate, keeps values across restarts. |
| Changing `DATABASE_USER`, `DATABASE_PASS` or `MINIO_*` in `.env` has no effect on the bundled services. | `POSTGRES_*` and `MINIO_ROOT_*` are applied when the data volume is first initialised; later changes only reach the application, which then fails to authenticate. | Either change the values back, or discard the volumes with `docker compose --env-file .env -f docker/docker-compose.yml down -v` (this deletes all data) and start again. |

## What each health check tests

The table is the list of `healthcheck` entries in the Compose files. Time to
`unhealthy` is the start period plus the retries, during which
`docker compose ps` shows `health: starting`.

| Service | Probe | Start period, retries | A failure means |
| --- | --- | --- | --- |
| `postgres` | `pg_isready -U $DATABASE_USER -d $DATABASE_NAME` | 10 s, 10 tries 10 s apart | PostgreSQL is not accepting connections. `pg_isready` does not authenticate, so wrong credentials pass here and fail later in `migrate`. |
| `redis` | `redis-cli ping` | 5 s, 10 tries 10 s apart | Redis is not answering. |
| `minio` | `curl -f http://localhost:9000/minio/health/live` | 10 s, 10 tries 10 s apart | MinIO is not serving. Full disks (`XMinioStorageFull` in its log) are the usual cause on a long-running host. |
| `etcd` | `etcdctl --endpoints=http://localhost:2379 endpoint health` | 10 s, 10 tries 10 s apart | etcd is not healthy; Milvus will not start until it is. |
| `milvus` | `curl -f http://localhost:9091/healthz` | 20 s, 10 tries 15 s apart | Milvus standalone has not finished starting, or cannot reach etcd or MinIO. |
| `vault` | `vault status -format=json` against `http://localhost:8200` | 10 s, 10 tries 10 s apart | The dev-mode server is not up or is sealed. |
| `api` | `GET http://localhost:9200/health/ready` with a 3 s timeout | 20 s, 5 tries 10 s apart | The API is not listening, or readiness answered `503`: database or object storage unreachable. The vector store is reported in the body but does not fail the probe. |
| `web` | `wget -q -O - http://127.0.0.1:5000/` | 20 s, 5 tries 10 s apart | The web server is not serving the UI. |
| `outbox-dispatcher` | `GET http://localhost:9201/metrics` with a 3 s timeout | 10 s, 5 tries 10 s apart | The dispatcher process is not serving metrics: it exited before starting the server (settings validation or plugin loading failed) or it is not running. |

`knowledge-ingest-worker`, `scheduler`, `migrate`, `bootstrap` and
`minio-init` have no health check: judge them by their exit code and their log.

## Start-up order

Nothing starts until what it waits for is ready, so a stuck service is often
waiting on another:

1. `postgres`, `redis`, `minio`, `etcd` and `vault` start together.
2. `minio-init` runs once `minio` is healthy; `milvus` starts once `etcd` and
   `minio` are healthy.
3. `migrate` runs once `postgres` is healthy.
4. `bootstrap` runs once `migrate` has completed successfully.
5. `api`, `knowledge-ingest-worker`, `outbox-dispatcher` and `scheduler` start
   once `bootstrap` has completed and the infrastructure they use is healthy
   (`api` and the knowledge worker also wait for `milvus` and `minio-init`).
6. `web` starts once `api` is healthy.

`docker compose ... ps -a` shows the one-shot jobs as `Exited (0)` when they
succeeded. Any other exit code stops the chain at that point.

## Starting over

`down` keeps the volumes, so data, the admin account and the initialised
credentials survive a restart. To discard everything and start from a clean
state:

```bash
docker compose --env-file .env -f docker/docker-compose.yml down -v
```

For the lite profile the equivalent is
`docker compose -f docker/docker-compose.lite.yml down -v`. Both delete all
data.
