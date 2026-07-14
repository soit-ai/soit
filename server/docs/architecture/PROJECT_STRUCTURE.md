# Project Structure Overview

This page summarizes the top-level layout and module boundaries for SOIT.

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
│   ├── kernel/               # Stable core (contracts/ports/specs/identity/runtime)
│   ├── modules/              # Product domains (agent/chat/workflow, etc.)
│   ├── adapters/             # Port implementations (LLM/vector/storage/secrets)
│   ├── infra/                # Infrastructure (DB/session, etc.)
│   ├── middleware/           # Middleware (request_id/error/envelope)
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

- `kernel/`: long-lived core capabilities; does not depend on `modules/`, `api/`, `adapters/`, or `infra/`.
- `modules/`: product domain logic; depends on `kernel/` and `adapters/`.
- `adapters/`: replaceable port implementations; no business logic.
- `api/`: transport layer and route orchestration; keep thin.
- `infra/`: database and infrastructure implementations.
- `settings/`: configuration and feature flags; no external calls.

Kernel data that comes from product or infrastructure layers must cross an
explicit provider boundary registered in `wiring/`. Current examples are
resource grants for identity checks and scoped egress policy lookup. Runtime
task status language and transition rules are defined in
`app/kernel/runtime/tasks/status.py`.

Runtime execution and persistence state is centralized under
`app/kernel/runtime/`:

- `runtime/db/models/`: all kernel-owned SQLModel table classes.
- `runtime/tasks/`: task service, repository, schemas, status, and task events.
- `runtime/threads/`: thread service, repository, schemas, and protocols.
- `runtime/runs/`: run/step/artifact/cost models, trace writer, run service, and exporters.
- `runtime/responses/`: response repository, service, schemas, and projection orchestrator.

Kernel extension rules:
- Concrete provider registration belongs in `app/wiring/`; tests enforce this.
- Port policy gateways share timeout/retry/run-id/error helper behavior from `app/kernel/ports/common/policy.py`.
- Runtime services should type persistence dependencies as Protocols; existing SQLModel repositories stay as default implementations.
- New SQLModel table classes must be added under `app/kernel/runtime/db/models/`; other kernel packages should remain pure logic, providers, ports, contracts, or orchestration.
- Kernel-owned outbox event payload versions are registered in `app/kernel/events/payload_registry.py`; unknown non-kernel event types remain compatible.
- Typed contract dataclasses are additive wrappers and must not change HTTP schemas or database JSON field shape unless separately versioned.

## Python Project Management (uv)

- Dependency config: `pyproject.toml`
- Dependency lockfile: `uv.lock`
- Common commands (from `/`):
  - `uv sync`
  - `uv run uvicorn app.main:app`
  - `uv run pytest`
