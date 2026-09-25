#!/usr/bin/env sh
set -e

# Wait for the database first: against infrastructure Compose does not start,
# nothing else orders this after the database is up.
python scripts/wait_for_database.py

# Apply database migrations to the latest revision. Call alembic from the
# synced environment directly; `uv run` would try to re-sync the virtualenv,
# which is read-only for the non-root runtime user.
alembic upgrade head
