# Contributing to SOIT

Thank you for contributing to SOIT. This repository contains the open-source
Community core: the agent runtime, workflow runtime, knowledge pipeline,
plugin/MCP basics, run/task ledger, model management, and local deployment
assets.

## Development Setup

Install backend dependencies from `server/`:

```powershell
uv sync
```

Install frontend dependencies from `web/`:

```powershell
npm install
```

For a local environment with supporting services, use the Docker quickstart in
[docs/quickstart.md](docs/quickstart.md). For hot reload development, see
[docs/development.md](docs/development.md).

## Quality Checks

Run focused checks first, then broaden to the relevant gate before opening a
pull request.

Backend checks from `server/`:

```powershell
uv run pytest
uv run lint-imports --config importlinter.ini
uv run ruff check app tests
uv run mypy app tests
```

Frontend checks from `web/`:

```powershell
npm run typecheck
npm run build
npm run test:e2e
```

## Documentation

Public documentation belongs in `docs/`, `server/docs/`, or `web/docs/`.
Keep local planning notes, private release evidence, and operator-specific
records out of this repository.

When changing a documented command, path, or release template, update the
corresponding tests under `server/tests/unit/` if they validate that artifact.

## Pull Requests

Before opening a pull request:

1. Keep changes scoped to one feature, fix, or documentation update.
2. Include tests or verification output for behavior changes.
3. Update public documentation when user-facing behavior changes.
4. Avoid committing secrets, local credentials, generated build output, or
   machine-specific evidence files.
