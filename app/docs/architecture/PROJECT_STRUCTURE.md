# Project Structure Overview

This page summarizes the top-level layout and module boundaries for SOIT-Pro.

## Root Layout

```
.
├── app/                      # Backend (FastAPI)
├── web/                      # Frontend (React Router)
├── docs/                     # Project-wide docs (public/product/general)
├── docker/                   # Container and orchestration assets
└── README.md                 # Project overview
```

## Backend app/ Layout

```
app/
├── app/                      # Application code
│   ├── api/                  # HTTP/WS/SSE transport layer (v1 routes and schemas)
│   ├── kernel/               # Stable core (contracts/ports/specs/identity/trace)
│   ├── modules/              # Product domains (agent/chat/workflow, etc.)
│   ├── adapters/             # Port implementations (LLM/vector/storage/secrets)
│   ├── infra/                # Infrastructure (DB/session, etc.)
│   ├── middleware/           # Middleware (request_id/error/envelope)
│   ├── plugins/              # Plugin SDK and loader
│   ├── settings/             # Configuration and env parsing
│   ├── utils/                # Shared utilities
│   ├── wiring/               # Dependency wiring
│   └── main.py               # FastAPI entry and router registration
├── docs/                     # Backend engineering/architecture/spec docs
├── tests/                    # Backend tests
├── scripts/                  # Scripts and tools
├── alembic/                  # Database migrations
├── pyproject.toml            # Dependencies and toolchain (uv)
└── uv.lock                   # uv lockfile
```

## Core Module Boundaries

- `kernel/`: long-lived core capabilities; does not depend on `modules/`.
- `modules/`: product domain logic; depends on `kernel/` and `adapters/`.
- `adapters/`: replaceable port implementations; no business logic.
- `api/`: transport layer and route orchestration; keep thin.
- `infra/`: database and infrastructure implementations.
- `settings/`: configuration and feature flags; no external calls.

## Python Project Management (uv)

- Dependency config: `app/pyproject.toml`
- Dependency lockfile: `app/uv.lock`
- Common commands (from `app/`):
  - `uv sync`
  - `uv run uvicorn app.main:app`
  - `uv run pytest`
