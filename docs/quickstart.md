# SOIT Quickstart

This quickstart is the Phase 1 local path for a new self-hosted SOIT environment. It documents the Docker stack, demo seed, and smoke/regression evidence needed before marking the 1.0 quickstart gate complete.

![SOIT workspace screenshot](assets/hero.png)

If containers fail to start, see [troubleshooting.md](./troubleshooting.md) for common causes (env-file, ports, Milvus, migrate/bootstrap logs).

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
