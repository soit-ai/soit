# docker/

Docker and docker-compose deployment assets for local/dev/prod.

Rules:
- Avoid environment-specific secrets in version control.
- Use env files and secret references.

## Quick Start (local)

1) Copy env file and edit values:
   - `cp .env.example .env`

2) Start dependencies + services:
   - `docker compose up -d`

3) Run migrations:
   - `docker compose run --rm api uv run alembic upgrade head`

4) Bootstrap admin user:
   - `docker compose run --rm api uv run python scripts/bootstrap_admin.py --email admin@example.com --password changeme123`

5) Open services:
   - API: `http://localhost:9200`
   - Web: `http://localhost:5000`
   - MinIO console: `http://localhost:9001`
   - Vault (dev): `http://localhost:8200`

Notes:
- Web build reads `VITE_BASE_URL` at build time. Rebuild the web image after changing it.
- Health checks are enabled for `api` and `web` in docker-compose.
- Vault runs in dev mode by default. The root token is controlled by `VAULT_DEV_ROOT_TOKEN_ID`.
- To process dataset ingestion tasks in the background, set `DATASET_INGEST_WORKER_ENABLED=true`.
- Alternatively, run the worker explicitly: `docker compose run --rm api uv run python scripts/ingest_worker.py`.

## One-shot bootstrap

You can run a single script that starts services, runs migrations, and creates a default admin.

- Bash (macOS/Linux/WSL): `bash docker/bootstrap.sh`
- PowerShell: `powershell -ExecutionPolicy Bypass -File docker/bootstrap.ps1`

Environment overrides:
- `ADMIN_EMAIL` (default: `admin@example.com`)
- `ADMIN_PASSWORD` (default: `changeme123`)

## Vault (dev) defaults

The compose file starts Vault in dev mode:
- URL: `http://localhost:8200`
- Token: `VAULT_DEV_ROOT_TOKEN_ID` (default `soit-vault-root`)

Set these in your `.env`:
- `VAULT_URL=http://vault:8200` (inside compose network)
- `VAULT_TOKEN=soit-vault-root`
