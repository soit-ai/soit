# SOIT Backend

Main backend workspace for SOIT.

- `app/kernel/`: long-term stable core (contracts, ports, specs, trace, security)
- `app/modules/`: product domains (services/repositories/models)
- `app/adapters/`: infra implementations (LLM/vector/storage/secrets/tools)
- `app/api/`: FastAPI transport layer (routers, SSE/WS)
- `docs/`: engineering/architecture/spec assets

## Overview

SOIT is an enterprise-grade governed agent platform providing agent building,
workflow orchestration, knowledge retrieval, plugin/MCP integration, and
runtime observability on a multi-tenant, front/back separated architecture.

The backend is Python 3.11 with FastAPI, SQLModel/SQLAlchemy, Alembic, and
Celery, backed by PostgreSQL, Redis, Milvus, MinIO, and Vault, with
OpenTelemetry-compatible tracing. Quality tooling is `ruff`, `pyright`, and
`pytest` via `uv`.

For the authoritative architecture and structure documentation, start with:

- [docs/README.md](docs/README.md)
- [docs/architecture/PROJECT_STRUCTURE.md](docs/architecture/PROJECT_STRUCTURE.md)
- [docs/engineering/ENGINEERING_GUIDE.md](docs/engineering/ENGINEERING_GUIDE.md)
