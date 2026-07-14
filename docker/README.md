# docker/

Docker Compose deployment assets for local self-hosted development and Phase 1
quickstart validation.

## Quick Start

From the repository root:

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up -d postgres redis minio etcd milvus vault migrate bootstrap api web knowledge-ingest-worker
```

Open:

- API: `http://localhost:9200`
- Web: `http://localhost:5000`
- MinIO console: `http://localhost:9001`
- Vault dev server: `http://localhost:8200`

## Bootstrap Helpers

The helper scripts run the same compose path and start the documented service
set:

- Bash: `bash docker/bootstrap.sh`
- PowerShell: `powershell -ExecutionPolicy Bypass -File docker/bootstrap.ps1`

Environment overrides:

- `BOOTSTRAP_ADMIN_EMAIL` (default: `admin@example.com`)
- `BOOTSTRAP_ADMIN_PASSWORD` (default: `changeme123`)
- `BOOTSTRAP_ADMIN_NAME` (default: `Admin`)
- `BOOTSTRAP_TENANT_NAME` (default: `default`)

## Evidence Gate

The Phase 1 quickstart gate is not complete until fresh service health, API/Web
health, demo seed, Chain A smoke, and regression evidence are captured and pass:

```bash
cd server
uv run python scripts/verify_quickstart_deployment.py ../docs/deployment/quickstart-deployment-evidence.example.json
```
