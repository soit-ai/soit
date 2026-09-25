# docker/

Docker Compose deployment assets for local self-hosted development and Phase 1
quickstart validation.

## Files

| File | Contents |
| --- | --- |
| `docker-compose.yml` | Quickstart entry point. Includes the three files below; defines nothing itself. |
| `docker-compose.infra.yml` | Bundled infrastructure: PostgreSQL, Redis, MinIO, Milvus with etcd, dev-mode Vault. |
| `docker-compose.app.yml` | Application processes: `migrate`, `bootstrap`, `api`, `web`, `knowledge-ingest-worker`, `outbox-dispatcher`, `scheduler`. |
| `docker-compose.deps.yml` | Makes the application wait for the bundled infrastructure. Only used through `docker-compose.yml`. |
| `docker-compose.images.yml` | Overlay that runs released images instead of building from source. |
| `docker-compose.production.yml` | Hardened production reference; bundles no infrastructure. |

All of the quickstart files use the project name `soit`, so volumes
(`soit_postgres_data`, ...), the network (`soit_default`) and service hostnames
are the same however the stack is started. Splitting the files did not rename
anything: an existing quickstart keeps its data.

Requires Docker Compose v2.24 or later.

## Quick Start

From the repository root:

```bash
cp .env.example .env
docker compose --env-file .env -f docker/docker-compose.yml up -d postgres redis minio etcd milvus vault migrate bootstrap api web knowledge-ingest-worker outbox-dispatcher
```

Open:

- API: `http://localhost:9200`
- Web: `http://localhost:5000`
- MinIO console: `http://localhost:9001`
- Vault dev server: `http://localhost:8200`

## Use Infrastructure You Already Run

Skip whichever bundled services you already operate. Point the application at
yours in `.env`, and always pass `--env-file .env`: the variables are read when
Compose interpolates the files, not only inside the containers.

### Everything external

```bash
docker compose --env-file .env -f docker/docker-compose.app.yml up -d
```

### Some external, some bundled

Start the bundled services you still need first, and wait until they are
healthy. Standalone, the application does not wait for infrastructure; only
`migrate` retries the database connection, for up to `DATABASE_WAIT_SECONDS`
(default 60).

```bash
# Example: your own PostgreSQL and Redis, bundled object storage, vectors and Vault.
docker compose --env-file .env -f docker/docker-compose.infra.yml up -d --wait minio minio-init etcd milvus vault
docker compose --env-file .env -f docker/docker-compose.app.yml up -d
```

Both commands address the same `soit` project, so the application reaches the
bundled services by their service names. Manage each part with its own file:
`down` on `docker-compose.app.yml` stops only the application, and the
"network is still in use" message it prints is expected. Compose may call the
other file's containers orphans; do not pass `--remove-orphans`, which would
remove them.

### Addresses

Inside a container `localhost` is the container itself. A service running on
the Docker host is reached as `host.docker.internal`; the application services
map that name to the host gateway, including on Linux. A service on another
machine is reached by its usual address.

| Component | Variables | Notes |
| --- | --- | --- |
| PostgreSQL | `DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_USER`, `DATABASE_PASS`, `DATABASE_NAME`, or a full `DATABASE_URL` | The bundled server is PostgreSQL 15. The user must be able to create tables in the database, since `migrate` runs Alembic. Size `max_connections` for every process's pool ([database-connections.md](../docs/operations/database-connections.md)); the bundled server uses 200. |
| Redis | `REDIS_URL`, `REDIS_HOST`, `REDIS_PORT`, `EVENT_BUS_REDIS_URL` | Set `REDIS_URL` and `EVENT_BUS_REDIS_URL` together. On a shared Redis, give SOIT its own database index, e.g. `redis://host.docker.internal:6379/3`. |
| Object storage | `STORAGE_URL`, `STORAGE_OPTIONS_JSON`, `STORAGE_AUTO_MKDIR` | Any S3-compatible store. `STORAGE_OPTIONS_JSON` carries `endpoint_url`, `key` and `secret`; its default names the bundled `minio:9000`. With `STORAGE_AUTO_MKDIR=true` the application creates the bucket. |
| Vector store | `MILVUS_HOST`, `MILVUS_PORT` | Milvus 2.5. For local development only, `VECTOR_BACKEND=pgvector` keeps vectors in PostgreSQL instead and needs the `vector` extension there. |
| Vault | `VAULT_URL`, `VAULT_TOKEN` | An empty `VAULT_URL` falls back to the bundled `http://vault:8200`, so without a Vault of your own, start the bundled one. |

Backups: `operations/compose_backup.py` and `compose_restore.py` dump
PostgreSQL and mirror MinIO through the bundled containers. Back up external
PostgreSQL and object storage with the tools you already use for them; the
[backup runbook](../docs/operations/backup-restore.md) lists what a complete
backup contains.

## Bootstrap Helpers

The helper scripts run the same compose path and start the documented service
set:

- Bash: `bash docker/bootstrap.sh`
- PowerShell: `powershell -ExecutionPolicy Bypass -File docker/bootstrap.ps1`

Environment overrides:

- `BOOTSTRAP_ADMIN_EMAIL` (default: `admin@example.com`)
- `BOOTSTRAP_ADMIN_PASSWORD` (default: `changeme123`)
- `BOOTSTRAP_ADMIN_NAME` (default: `Admin`)
- `BOOTSTRAP_TENANT_NAME` (default: `default`)

## Evidence Gate

The Phase 1 quickstart gate is not complete until fresh service health, API/Web
health, demo seed, Chain A smoke, and regression evidence are captured and pass:

```bash
cd server
uv run python scripts/verify_quickstart_deployment.py ../docs/deployment/quickstart-deployment-evidence.example.json
```
