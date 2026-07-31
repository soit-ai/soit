# Quality Gate

This project treats schema/service drift as a merge blocker. Run the blocking checks locally before opening a PR.

## Blocking Backend Gate

From `server/`:

```bash
uv sync
uv run alembic heads
uv run pytest tests/unit/test_fresh_install_migration.py -q
uv run pytest tests/postgres -q
uv run pytest tests/unit/test_egress_policy.py tests/unit/test_governed_http_fetch.py tests/unit/test_governed_egress_paths.py tests/unit/test_scoped_secrets_port.py tests/unit/test_resource_permissions.py tests/unit/test_agent_service.py -q
uv run lint-imports --config importlinter.ini
uv run ruff check app/modules/agent/application/schemas.py app/modules/agent/application/service.py app/modules/agent/application/application_service.py app/api/v1/agent/handlers.py tests/unit/test_agent_service.py tests/unit/test_agent_rag.py tests/integration/test_agent_publish_and_execute.py tests/entrypoints/test_agent_api.py tests/entrypoints/test_agent_stream_api.py --select F,E402,I
uv run pytest tests/unit/test_agent_service.py tests/unit/test_agent_rag.py tests/integration/test_agent_publish_and_execute.py tests/entrypoints/test_agent_api.py tests/entrypoints/test_agent_stream_api.py -q
uv run pytest tests/entrypoints/test_api_route_convergence.py tests/integration/test_enterprise_agent_mvp.py -q
uv run python scripts/evaluate_support_ticket_regression.py --json-output ../artifacts/support-ticket-regression/report-current.json
uv run pytest tests/integration/test_support_ticket_regression_evaluator.py -q
uv run pytest tests/unit -q
uv run pytest tests/entrypoints -q
uv run pytest tests/integration -q
uv run pytest tests/test_spec_validation.py tests/test_model_scope_audit.py tests/test_trace_emission.py -q
```

`tests/postgres/` is intentionally separate from the SQLite-backed unit-test
fixtures. It requires `DATABASE_URL` to reference a migrated PostgreSQL database
and verifies concurrent lease ownership, `FOR UPDATE SKIP LOCKED` worker claims,
expired-lease reclaim of orphaned work, outbox recovery, response idempotency,
serialized event sequencing, and native JSON query behavior. SQLite ignores
`SKIP LOCKED`, so lease exclusivity is only ever proven here.
A skipped PostgreSQL suite is not a passing release gate.

Point `DATABASE_URL` at a dedicated acceptance database rather than a working
development database:

```bash
DATABASE_URL="postgresql://<user>:<password>@<host>:5432/db_soit_pg_acceptance" uv run alembic upgrade head
DATABASE_URL="postgresql://<user>:<password>@<host>:5432/db_soit_pg_acceptance" uv run pytest tests/postgres -q
```

## Independent Release Acceptance

CI and developer-operated smoke tests do not satisfy the independent acceptance
gate. Before release sign-off, two or three non-code authors must independently
complete the clean-install and empty-workspace procedure in
`docs/deployment/independent-release-acceptance.md`. Validate the final private
evidence package in strict mode:

```bash
cd server
uv run python scripts/verify_independent_release_acceptance.py \
  /path/to/independent-release-acceptance.json \
  --evidence-root /path/to/private-release-evidence
```

The gate remains incomplete until every environment, run, and signature reference
exists and the strict verifier passes.

## Blocking Frontend Gate

From `web/`:

```bash
npm ci
npm run typecheck
npm run build
npm run budget
npx playwright install chromium
npm run test:e2e
npm run test:e2e:real
```

The regular Playwright suite is deterministic and may intercept API calls. The
separate `test:e2e:real` release gate must run against a freshly migrated
PostgreSQL database and a live API. It covers the empty-workspace journey,
Observe run evidence, and API key scope enforcement; the governance specs in
particular only mean anything against a live server, because a mocked response
would assert the frontend assumption rather than the backend rule. It creates a new tenant and empty workspace,
then completes the Knowledge, Agent publish/execute, Observe, and Workflow
publish/execute journey without `page.route()` or seeded product records. Set
`SOIT_REAL_API_BASE_URL` and `PLAYWRIGHT_BASE_URL` when the API or web ports
differ from `9200` and `5000`.

To reproduce this gate locally, start the API with the same environment CI
uses. `SOIT_TESTING=1` is required, not optional: without it the container
resolves real model providers and every spec fails at
`MODEL_RUNTIME_NOT_FOUND`, because a workspace created by sign-up has no model
route. Knowledge ingestion additionally needs the dedicated worker running,
since the API no longer performs ingestion in-process.

```bash
cd server
SOIT_TESTING=1 ALLOW_PUBLIC_REGISTRATION=true ENVIRONMENT=development \
  EVENT_BUS_BACKEND=memory RESPONSE_INTERACTION_INLINE_EXECUTION=true \
  OUTBOX_DISPATCHER_ENABLED=false KNOWLEDGE_INGEST_WORKER_ENABLED=false \
  DATABASE_URL=<migrated database> \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 9200
```

```bash
cd server
SOIT_TESTING=1 KNOWLEDGE_INGEST_WORKER_ENABLED=true KNOWLEDGE_INGEST_WORKER_MAX_TASKS=0 \
  DATABASE_URL=<same database> \
  uv run python scripts/ingest_worker.py
```

```bash
cd web
SOIT_REAL_API_BASE_URL=http://127.0.0.1:9200/api/v1 npm run test:e2e:real
```

## Blocking Container Gate

The quality workflow validates the Compose model, builds the backend image,
applies Alembic migrations from that image, starts the API as a single Uvicorn
process, and requires `/health/ready` to report `ready` against PostgreSQL. It
also starts the dedicated outbox dispatcher and knowledge worker; the dispatcher
must expose its metric and the knowledge worker must remain running. A failed
image build, migration, startup, worker smoke, or readiness probe blocks the
workflow.

Run the configuration check locally from the repository root:

```bash
docker compose -f docker/docker-compose.yml config --quiet
```

When Docker is available, build the same backend image used by the CI smoke job:

```bash
docker build --tag soit-api:local ./server
```

## Enterprise MVP Demo Smoke

Use this after migrations are available on the target database:

```bash
cd server
uv run python scripts/bootstrap_enterprise_mvp.py
uv run pytest tests/integration/test_enterprise_agent_mvp.py -q
```

## Support/Ticket Regression Gate

The current regression focus is the customer support/ticket loop only: refund policy knowledge, support agent response, ticket triage workflow, ticket tool call, citations, audit, cost, and Observe run detail evidence. Commercial collateral, website copy, pricing, enterprise capability matrices, and customer PoC sales material are out of scope for this gate.

From `server/`:

```bash
uv run python scripts/evaluate_support_ticket_regression.py --json-output ../artifacts/support-ticket-regression/report-current.json
uv run pytest tests/integration/test_support_ticket_regression_evaluator.py -q
```

This is a blocking non-Docker backend gate. Run it against a database initialized through the current Alembic head; GitHub Actions provisions an empty PostgreSQL database and applies the explicit baseline plus all supported forward revisions before this gate. The evaluator uses the deterministic `model:test:*` path, bootstraps the Enterprise MVP seed when needed, executes the fixed support/ticket golden prompt set, and exits non-zero if any case fails. The JSON report is machine readable and includes `pass/fail`, failure reasons, `run_id`, `response_id`, `tool_call_count`, `citation_count`, `cost`, and `latency_ms` for each case.

Every passing report must include at least one policy answer case with a citation to `refund-policy.md` and one ticket workflow case with a tool call, child workflow run, audit evidence, citation evidence, and cost evidence.

## Governance Evidence

The support/ticket MVP is also the governance proof path. When the corresponding feature is implemented, the demo evidence must show:

- Permission-scoped Agent, Knowledge, Workflow, Tool, Plugin, or MCP bindings.
- Secret access through configured secret references rather than raw payload values.
- Egress policy status for external HTTP or tool-adapter calls.
- Audit records for privileged operations, approvals, and tool execution.
- Cost attribution on the run detail and regression JSON report.
- Trace timeline covering response events, run steps, tool calls, and child workflow runs.
- Replayable run detail that lets an operator reconstruct what happened without reading raw database rows.

## Observe Acceptance

Quality gate commands such as `pytest`, `lint-imports`, `typecheck`, `build`, and Playwright e2e are not recorded as Observe runs. Observe validates application runtime data only: Agent, Workflow, Knowledge, Response, Tool, Cost, Audit, and Citation records created by demo or product operations.

After running the Enterprise MVP demo or the support/ticket regression evaluator, open `/observe?range=24h` and confirm the recent application run is visible. Then use `/observe/runs?include_observe_summary=true` with the quick filters for tool calls, citations, and audits to locate the same run and inspect its detail page.

The Run Explorer entry must remain clickable from the Observe dashboard. The run detail page for a support/ticket regression run must show response events, run steps, tool calls, child workflow runs, costs, citations, and audits.

For the full local Compose acceptance path when the infrastructure stack is available:

```bash
docker compose -f docker/docker-compose.yml up -d postgres redis minio etcd milvus vault migrate bootstrap api web knowledge-ingest-worker outbox-dispatcher
curl http://localhost:9200/api/v1/health/ready
curl http://localhost:5000/
docker compose -f docker/docker-compose.yml ps knowledge-ingest-worker
curl http://localhost:9201/metrics
```

Expected: the API is ready, the web app responds, and `knowledge-ingest-worker` remains running.

## Blocking Static Gates

These checks are blocking in CI. The strict Pyright scope is intentionally progressive; expand `server/pyrightconfig.json` as typed boundaries are cleaned up, without weakening the existing set.

```bash
cd server
uv run ruff check app tests
uv run pyright
uv run lint-imports --config importlinter.ini
```

Frontend build output is also budgeted. After `npm run build`, `npm run budget`
reads the generated SPA entry page and fails when initial JavaScript exceeds
840,000 bytes or any JavaScript chunk exceeds 2,016,000 bytes. The
repository-local `web/bundle-budget.json` records these explicit limits; change
them only with measured build evidence and review.

## Contract Rules

- Public API schemas validate transport payloads only.
- Application services resolve published versions into internal runtime requests before execution.
- Runtime services must not read fields that only exist in HTTP payloads or frontend service types.
- Agent execution model/tool/knowledge/workflow/skill/plugin bindings come from the published agent version, not execute payload overrides.
- Import boundaries in `server/importlinter.ini` are part of the quality gate.
- The Agent, Plugin, and Security cross-domain read paths use explicit application ports; new direct cross-domain ORM imports fail CI.
