#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required but not found in PATH."
  exit 1
fi

docker compose up -d
docker compose run --rm api uv run alembic upgrade head

ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-changeme123}"

docker compose run --rm api uv run python scripts/bootstrap_admin.py --email "${ADMIN_EMAIL}" --password "${ADMIN_PASSWORD}"
