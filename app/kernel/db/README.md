# kernel/db/

Database infrastructure and base repository patterns.

Contains:
- engine/session/transaction
- scope-aware repository base (tenant_id + workspace_id enforced)
- pagination helpers
- migration glue (if any)

Rules:
- Domain table models live in `modules/domains/*`.
