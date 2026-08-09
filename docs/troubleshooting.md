# Troubleshooting (local Docker quickstart)

Common first-run failures and how to fix them. For the happy path, see [quickstart.md](./quickstart.md).

## Symptom → cause → fix

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Compose variables empty / containers get wrong hostnames or blank secrets | `.env` not loaded into Compose interpolation | Always pass the env file: `docker compose --env-file .env -f docker/docker-compose.yml up -d …`. Plain `docker compose up` does **not** automatically interpolate every variable from a root `.env` for all setups. |
| `bind: address already in use` for web/API/Postgres/Redis/Vault | Host port already taken | Override the published port via env (see `.env.example`): e.g. `WEB_PUBLISHED_PORT`, `API_PUBLISHED_PORT`, `POSTGRES_PUBLISHED_PORT`, `REDIS_PUBLISHED_PORT`, `VAULT_PUBLISHED_PORT` / port `8200`. Then recreate: `docker compose --env-file .env -f docker/docker-compose.yml up -d`. |
| Vault fails or UI cannot reach secrets on port 8200 | Another process bound `8200` | Free the port or set the Vault published-port override in `.env`, then `up -d vault` again. |
| Milvus stays unhealthy / API cannot talk to vector store | etcd or MinIO not ready; Milvus started too early | Start dependencies first: `docker compose --env-file .env -f docker/docker-compose.yml up -d etcd minio`, wait until healthy, then `up -d milvus`. Or bring the full stack up and wait for healthchecks: `docker compose … ps` / `docker compose … logs -f milvus`. |
| `migrate` or `bootstrap` container exited non-zero; stack half-ready | One-shot job failed (DB not ready, bad env, migration error) | Inspect logs: `docker compose --env-file .env -f docker/docker-compose.yml logs migrate` and `… logs bootstrap`. Fix the reported error (connection string, permissions, SQL), then re-run that service: `docker compose --env-file .env -f docker/docker-compose.yml up migrate bootstrap`. |
| Web opens but login fails | Bootstrap admin not created / wrong credentials | Confirm `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` in `.env`, re-run `bootstrap`, and use those credentials. |
| Changes to `.env` seem ignored | Containers still running with old env | Recreate after edits: `docker compose --env-file .env -f docker/docker-compose.yml up -d --force-recreate`. |

## Reading one-shot job logs

`migrate` and `bootstrap` are short-lived. If they exit quickly:

```bash
docker compose --env-file .env -f docker/docker-compose.yml ps -a
docker compose --env-file .env -f docker/docker-compose.yml logs migrate
docker compose --env-file .env -f docker/docker-compose.yml logs bootstrap
```

Look for connection refused (Postgres not ready yet), missing env vars, or migration SQL errors. Fix, then re-run only those services.

## Port override checklist

If the default host ports clash with local tools, set the `*_PUBLISHED_PORT` variables from `.env.example` before `up`. Prefer changing published ports over stopping unrelated host services when you need both stacks.

## Still stuck?

1. `docker compose --env-file .env -f docker/docker-compose.yml ps`
2. Collect logs for the failing service (`logs <service>`).
3. Open an issue with the compose command you used (redact secrets) and the last ~50 log lines.
