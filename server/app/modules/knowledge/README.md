# modules/knowledge/

Internal storage/runtime backend for the public **knowledge** capability.

Place:
- `domain/`: SQLModel tables and internal domain entities
- `infra/`: scope-aware repositories and parsers
- `runtime/`: ingest/retrieval/indexing internals
- `application/`: runtime service used by the northbound knowledge application layer

Rules:
- Treat `modules/knowledge` as the northbound product boundary.
- Do not reintroduce any legacy knowledge naming.
- Keep tenant/workspace scope enforcement intact.

Workbench:
- `GET /api/v1/knowledge/workbench` aggregates knowledge inventory, index health, ingest state, and retrieval run metrics for the Knowledge workspace landing page.
- `GET /api/v1/knowledge/workbench/items` returns filtered, paginated table rows without changing the aggregate endpoint contract.
