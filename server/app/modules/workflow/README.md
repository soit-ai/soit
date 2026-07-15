# modules/workflow/

Domain: **workflow**.

Place:
- models.py (SQLModel tables)
- schemas.py (Pydantic)
- repository.py (DB access using scope-aware base)
- service.py (business logic)
- events.py (optional domain events)

Rules:
- Enforce tenant/workspace scope.
- Validate specs against kernel schemas if applicable.

Workbench:
- `GET /api/v1/workflows/workbench` aggregates workflow metrics and tab counts for the workspace landing page.
- `GET /api/v1/workflows/workbench/items` returns filtered, paginated table rows without changing the aggregate endpoint contract.
