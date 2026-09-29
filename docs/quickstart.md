# SOIT Quickstart

This quickstart is the Phase 1 local path for a new self-hosted SOIT environment. It documents the Docker stack, demo seed, and smoke/regression evidence needed before marking the 1.0 quickstart gate complete.

![SOIT workspace screenshot](assets/hero.png)

## Start the Local Stack

From the repository root:

```bash
cp .env.example .env
docker compose --env-file .env -f docker/docker-compose.yml up -d postgres redis minio etcd milvus vault migrate bootstrap api web knowledge-ingest-worker outbox-dispatcher
```

Open:

- Web UI: `http://localhost:5000`
- API docs and API base: `http://localhost:9200`

Sign in with `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` from `.env`.

If a service does not come up, [troubleshooting.md](troubleshooting.md) maps
the symptoms to their causes and says what each health check tests.

Already running PostgreSQL, Redis or another piece of the infrastructure? The
application and the bundled infrastructure are separate Compose files, so you
can start only what you are missing. See
[Use Infrastructure You Already Run](../docker/README.md#use-infrastructure-you-already-run).

Trying SOIT on a small machine? [minimal-topology.md](minimal-topology.md)
says which of the twelve services a demo can leave out and what stops working
when it does.

## Published Ports

Every host port of the quickstart topology is published through a
`*_PUBLISHED_PORT` variable. Set one in `.env` when a service on your machine
already owns the default; only the host side changes, the container port and
the service-to-service addresses (`postgres:5432`, `minio:9000`, ...) stay
the same.

| Variable | Service | Host port (default) | Container port | What it exposes |
| --- | --- | --- | --- | --- |
| `DATABASE_PUBLISHED_PORT` | `postgres` | 5432 | 5432 | PostgreSQL, for `psql` and the backup scripts |
| `REDIS_PUBLISHED_PORT` | `redis` | 6379 | 6379 | Redis |
| `MINIO_API_PUBLISHED_PORT` | `minio` | 9000 | 9000 | The S3 API of the bundled object store |
| `MINIO_CONSOLE_PUBLISHED_PORT` | `minio` | 9001 | 9001 | The MinIO web console |
| `ETCD_PUBLISHED_PORT` | `etcd` | 2379 | 2379 | The etcd client API that Milvus uses |
| `MILVUS_PUBLISHED_PORT` | `milvus` | 19530 | 19530 | The Milvus gRPC API |
| `MILVUS_METRICS_PUBLISHED_PORT` | `milvus` | 9091 | 9091 | Milvus metrics and its `/healthz` probe |
| `VAULT_PUBLISHED_PORT` | `vault` | 8200 | 8200 | The dev-mode Vault API and UI |
| `API_PUBLISHED_PORT` | `api` | 9200 | 9200 | The SOIT API: `/api/v1`, the OpenAI-compatible `/v1`, `/mcp` and `/health` |
| `WEB_PUBLISHED_PORT` | `web` | 5000 | 5000 | The web UI |

Notes:

- The variables are read when Compose interpolates the files, so pass
  `--env-file .env`. `.env.example` lists `DATABASE_PUBLISHED_PORT`,
  `MINIO_API_PUBLISHED_PORT` and `MINIO_CONSOLE_PUBLISHED_PORT`; add the
  others to `.env` as you need them.
- The `web` image is built with `VITE_BASE_URL`, `http://localhost:9200/api/v1`
  by default. After changing `API_PUBLISHED_PORT`, build the web image from
  source with `VITE_BASE_URL=http://localhost:<port>/api/v1`; the released
  `web` image only knows the default.
- The `outbox-dispatcher` metrics port (`9201`) is exposed on the Compose
  network only and is not published.
- The lite profile (`docker/docker-compose.lite.yml`) publishes only
  `API_PUBLISHED_PORT` and `WEB_PUBLISHED_PORT`; its PostgreSQL and Redis are
  not reachable from the host.

## Seed the Demo Workspace

After migrations are available, seed the deterministic Phase 1 demo data:

```bash
cd server
uv run python scripts/bootstrap_enterprise_mvp.py
```

The seed is idempotent and creates or updates:

- sample Provider and test models
- sample Knowledge base with `refund-policy.md`
- sample Agent bound to the model, knowledge, and tool
- sample Workflow for support ticket triage

For richer Observe, Task, Run, approval, and failure-state demos:

```bash
uv run python scripts/seed_enterprise_mvp_scenarios.py --reset
```

## Verify the Demo Path

Run the backend smoke test for the seeded Agent / Knowledge / Workflow path:

```bash
uv run pytest tests/integration/test_enterprise_agent_mvp.py -q
```

Run the support-ticket regression evaluator:

```bash
uv run python scripts/evaluate_support_ticket_regression.py --json-output ../artifacts/support-ticket-regression/report-current.json
```

The report should include citation evidence, tool-call evidence, child workflow run evidence, audit evidence, and cost evidence.

## Manual UI Check

Use the screenshot anchor above (`docs/assets/hero.png`) as the first-viewport visual reference. Then verify:

1. ModelHub shows the seeded test provider and models.
2. Knowledge contains the seeded refund policy document.
3. Agent can answer a refund-policy question with a citation.
4. Workflow can execute the support-ticket triage path.
5. Runs and Observe show response events, run steps, tool calls, child workflow runs, costs, citations, and audits.

## Docker Smoke Evidence

Before checking the roadmap Docker/Quickstart item, capture fresh output for:

```bash
curl http://localhost:9200/health/ready
curl http://localhost:5000/
docker compose -f docker/docker-compose.yml ps knowledge-ingest-worker
docker compose -f docker/docker-compose.yml ps outbox-dispatcher
```

Expected: API ready, web app responding, and both `knowledge-ingest-worker` and `outbox-dispatcher` healthy or running.

Copy `docs/deployment/quickstart-deployment-evidence.example.json` to `docs/deployment/quickstart-deployment-evidence.json`, replace all `evidenceRef` values with the captured fresh outputs, and validate it from `server/` with repository-root checks enabled:

```bash
uv run python scripts/verify_quickstart_deployment.py ../docs/deployment/quickstart-deployment-evidence.json --repo-root ..
```

The verifier requires the full Docker service set, per-service healthy status and unique service evidence refs, startup within 10 minutes, API/Web/worker health evidence, demo seed evidence, Chain A smoke evidence, regression output evidence, unique check evidence refs, and local evidence files that exist under the repository root.

## Database Migration Paths

SOIT 1.0 supports a fresh install through head `20260803090000` and an explicit N-1 upgrade from `20260718140000`. Other historical development snapshots are unsupported; see the [migration runbook](release-migration.md).

## Model Provider Support

For the 1.0 ModelHub provider support matrix and live credential spot-check scope, see [docs/model-provider-support.md](model-provider-support.md).

For the 1.0 owner UI spot-check and manual Chain A/B acceptance record, copy `docs/deployment/phase1-manual-acceptance-evidence.example.json` to `docs/deployment/phase1-manual-acceptance-evidence.json`, replace all `evidenceRef` values with real screenshots or command output, then validate it from `server/` with repository-root checks enabled:

```bash
uv run python scripts/verify_phase1_manual_acceptance.py ../docs/deployment/phase1-manual-acceptance-evidence.json --repo-root ..
```

The manual acceptance verifier requires unique route screenshot evidence refs, unique desktop/mobile viewport evidence refs per route, unique Chain A/B acceptance evidence refs, and real local evidence files when `--repo-root` is used.
