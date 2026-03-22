#!/usr/bin/env sh
set -e

# Apply database migrations to the latest revision.
uv run alembic upgrade head
