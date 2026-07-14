# app/docs/

Backend engineering and architecture documentation for SOIT.

- `architecture/`: backend boundaries, kernel contracts, data model notes
- `engineering/`: development workflow and engineering guidance

Current baseline:

- Root platform architecture lives under [../../docs/PLATFORM_ARCHITECTURE.md](../../docs/PLATFORM_ARCHITECTURE.md)
- Public backend entry points are now centered on `/api/v1/agents`, `/api/v1/threads`, `/api/v1/tasks`, `/api/v1/knowledge`, `/api/v1/workflows`, `/api/v1/runs`, `/api/v1/plugins`, and `/api/v1/responses`
