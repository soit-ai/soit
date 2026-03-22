# app/docs/

Backend engineering and architecture documentation for SOIT-Pro.

- `architecture/`: backend boundaries, kernel contracts, data model notes
- `engineering/`: development workflow and engineering guidance

Current baseline:

- Root architecture guardrails live under [../../docs/architecture](../../docs/architecture)
- Historical refactor plans live under [../../docs/archive](../../docs/archive)
- Public backend entry points are now centered on `/api/v1/agents`, `/api/v1/threads`, `/api/v1/tasks`, `/api/v1/knowledge`, `/api/v1/workflows`, `/api/v1/runs`, `/api/v1/plugins`, and `/api/v1/responses`
