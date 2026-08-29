# routes/agents/

Agent-centered frontend routes land here during the refactor.

- The workspace landing page reads `GET /api/v1/agents/workbench` for metrics, tabs, and sidebar stats.
- The right-side table reads `GET /api/v1/agents/workbench/items` for filtered, paginated rows.
