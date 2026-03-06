# Agent Task Template (SOIT-Pro)

## Goal
- Deliverable (one sentence describing the outcome):

## Context
- Affected area: backend(app) / frontend(web) / docs / infra
- Relevant docs (review first):
  - app/docs/README.md
  - app/docs/architecture/README.md
  - app/docs/architecture/PROJECT_STRUCTURE.md
  - web/docs/README.md
  - web/docs/PROJECT_STRUCTURE.md

## Scope
- In scope:
- Out of scope:

## Plan
- Files to change:
- New tests:
- Migration:
- Risks & rollback:

## Implementation Notes
- Boundaries: kernel/ does not depend on modules/; adapters/ contains no business logic; api/ orchestrates only.
- Backend commands (from app/): `uv sync`, `uv run uvicorn app.main:app`, `uv run pytest`
- Frontend structure (web/): pages/components/services/stores/hooks/styles/assets/i18n/config
- Compatibility: keep existing directories and naming conventions; avoid unrelated dependencies.

## Acceptance Checklist
- [ ] Works end-to-end
- [ ] Tests added/passed (if behavior changed)
- [ ] Observability added (logs/metrics/traces if needed)
- [ ] Docs updated (when public behavior changes)
