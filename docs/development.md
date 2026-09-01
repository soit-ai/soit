# SOIT Development

This guide covers local development with hot reload. For the single-command
Docker path, use [quickstart.md](quickstart.md).

## Backend

Run backend commands from `server/`:

```powershell
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 9200
```

The LiteLLM runtime adapter ships as a core dependency, so `uv sync` installs everything workspace-managed LiteLLM providers need.

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

### Milvus Lite For Local Debugging

`MILVUS_MODE` selects the vector store the backend talks to. The default,
`server`, connects to a Milvus deployment at `MILVUS_HOST:MILVUS_PORT`.
`lite` runs the embedded Milvus Lite engine against a local file, so knowledge
ingestion and retrieval work without the `milvus`, `etcd`, and `minio`
containers:

```powershell
$env:MILVUS_MODE = "lite"
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 9200
```

The database file is `MILVUS_LITE_FILE`, `./.milvus/soit_lite.db` by default,
resolved against `server/` and ignored by Git. Its directory is created on the
first connection.

The switch is for debugging only:

- Milvus Lite publishes no Windows build. On Windows, run the backend under WSL
  or keep `MILVUS_MODE=server`. Windows fails the connection with a message
  saying so rather than an import error.
- Milvus Lite implements the `FLAT` index only, so `lite` indexes collections
  exhaustively instead of with `IVF_FLAT`. Recall matches a server; latency does
  not, once collections grow.
- One process owns the file, and nothing else can read it. Startup refuses
  `lite` when `ENVIRONMENT=production`.
