# Quality Gate

This project treats schema/service drift as a merge blocker. Run the blocking checks locally before opening a PR.

## Blocking Backend Gate

From `server/`:

```bash
uv sync
uv run lint-imports --config importlinter.ini
uv run ruff check app/modules/agent/application/schemas.py app/modules/agent/application/service.py app/modules/agent/application/application_service.py app/api/v1/agent/handlers.py tests/unit/test_agent_service.py tests/unit/test_agent_rag.py tests/integration/test_agent_publish_and_execute.py tests/entrypoints/test_agent_api.py tests/entrypoints/test_agent_stream_api.py --select F,E402,I
uv run pytest tests/unit/test_agent_service.py tests/unit/test_agent_rag.py tests/integration/test_agent_publish_and_execute.py tests/entrypoints/test_agent_api.py tests/entrypoints/test_agent_stream_api.py -q
uv run pytest -q
```

## Blocking Frontend Gate

From `web/`:

```bash
npm ci
npm run typecheck
npx playwright install chromium
npm run test:e2e
```

## Strict Debt Checks

These checks run in CI as non-blocking debt reports until the existing lint/mypy backlog is burned down:

```bash
cd server
uv run ruff check app tests
uv run mypy app tests
```

## Contract Rules

- Public API schemas validate transport payloads only.
- Application services resolve published versions into internal runtime requests before execution.
- Runtime services must not read fields that only exist in HTTP payloads or frontend service types.
- Agent execution model/tool/knowledge/workflow/skill/plugin bindings come from the published agent version, not execute payload overrides.
- Import boundaries in `server/importlinter.ini` are part of the quality gate.
- Existing direct import-boundary debt is explicitly baselined in `server/importlinter.ini`; new direct boundary violations should fail CI.
