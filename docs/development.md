# SOIT Development

This guide covers local development with hot reload. For the single-command
Docker path, use [quickstart.md](quickstart.md).

## Backend

Run backend commands from `server/`:

```powershell
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 9200
```

For workspace-managed LiteLLM providers, install the optional runtime adapter:

```powershell
uv sync --extra llm-litellm
```

Useful backend checks:

```powershell
uv run pytest
uv run lint-imports --config importlinter.ini
uv run ruff check app tests
uv run pyright
```

## Frontend

Run frontend commands from `web/`:

```powershell
npm install
npm run dev
```

Useful frontend checks:

```powershell
npm run typecheck
npm run build
npm run test:e2e
```

## Supporting Services

The application expects PostgreSQL, Redis, Milvus, MinIO, and Vault for the
full local stack. You can start those services with the Docker Compose files
under `docker/`, then run the backend and frontend in hot reload mode from
`server/` and `web/`.

Keep local data and credentials out of commits. Do not commit generated
evidence files, screenshots, database dumps, or environment-specific records.
