#!/usr/bin/env sh
set -e

# Apply database migrations to the latest revision. Call alembic from the
# synced environment directly; `uv run` would try to re-sync the virtualenv,
# which is read-only for the non-root runtime user.
alembic upgrade head
