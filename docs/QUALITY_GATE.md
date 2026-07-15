# Quality Gate

This project treats schema/service drift as a merge blocker. Run the blocking checks locally before opening a PR.

## Blocking Backend Gate

From `server/`:

```bash
uv sync
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

## Blocking Frontend Gate

From `web/`:

```bash
npm ci
npm run typecheck
npm run build
npm run budget
npx playwright install chromium
npm run test:e2e
```

## Blocking Container Gate

The quality workflow validates the Compose model, builds the backend image, applies Alembic migrations from that image, starts the API as a single Uvicorn process, and requires `/health/ready` to report `ready` against PostgreSQL. A failed image build, migration, startup, or readiness probe blocks the workflow.

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

This is a blocking non-Docker backend gate. Run it against a migrated local database or an existing local development database; GitHub Actions provisions PostgreSQL and runs Alembic migrations before this gate. The evaluator uses the deterministic `model:test:*` path, bootstraps the Enterprise MVP seed when needed, executes the fixed support/ticket golden prompt set, and exits non-zero if any case fails. The JSON report is machine readable and includes `pass/fail`, failure reasons, `run_id`, `response_id`, `tool_call_count`, `citation_count`, `cost`, and `latency_ms` for each case.

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

These checks are blocking in CI. The strict mypy scope is intentionally progressive; expand `server/mypy-core.ini` as typed boundaries are cleaned up, without weakening the existing set.

```bash
cd server
uv run ruff check app tests
uv run mypy --config-file mypy-core.ini
uv run lint-imports --config importlinter.ini
```

Frontend build output is also budgeted. After `npm run build`, `npm run budget` reads the generated SPA entry page and fails when initial JavaScript exceeds 420,000 bytes or any JavaScript chunk exceeds 1,016,000 bytes. The repository-local `web/bundle-budget.json` records these explicit limits; change them only with measured build evidence and review.

## Contract Rules

- Public API schemas validate transport payloads only.
- Application services resolve published versions into internal runtime requests before execution.
- Runtime services must not read fields that only exist in HTTP payloads or frontend service types.
- Agent execution model/tool/knowledge/workflow/skill/plugin bindings come from the published agent version, not execute payload overrides.
- Import boundaries in `server/importlinter.ini` are part of the quality gate.
- The Agent, Plugin, and Security cross-domain read paths use explicit application ports; new direct cross-domain ORM imports fail CI.
