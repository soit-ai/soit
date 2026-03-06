# scripts/

Developer and ops scripts (one-off tasks).

Rules:
- Must be safe and clearly documented.
- Prefer idempotent scripts.

Available:
- `dataset_ingest_worker.py`: run dataset ingestion tasks for a tenant/workspace.
- `bootstrap_admin.py`: create a default admin user/tenant/workspace.
- `migrate.sh`: apply database migrations (alembic upgrade head).
- `smoke/run_all.py`: run release smoke tests (workflow/dataset/chat/secrets).
