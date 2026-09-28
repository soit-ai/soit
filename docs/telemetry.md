# Anonymous telemetry

SOIT sends nothing unless an operator turns telemetry on. With it on, the API
process sends one small report a day about the day before, so the project can
count installations, versions and how much governed work they do. Nothing
else leaves the deployment.

## Turning it on

```bash
TELEMETRY_ENABLED=true
# Optional: where reports go (this is the default).
TELEMETRY_ENDPOINT=https://soit.ai/api/telemetry
```

Once an hour the process checks whether yesterday's report (UTC) has been
sent, and sends it if not. Several API replicas send it once between them. A
report that cannot be delivered is tried again at the next check; failures
are logged at `WARNING` and never affect the runtime. Processes started with
`SOIT_ROLE=gateway` send nothing.

## What a report holds

See the exact report the next send would carry, whether telemetry is on or
not, as a tenant admin:

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:9200/api/v1/diagnostics/telemetry
```

```json
{
  "schema": 1,
  "installation_id": "3f2c7e0a-5b8d-4c1e-9a2f-6d4b8e1c0a9f",
  "version": "1.3.0",
  "edition": "community",
  "day": "2026-09-28",
  "deployment": {
    "environment": "production",
    "role": "all",
    "vector_backend": "pgvector",
    "storage": "file",
    "secrets_backend": "vault"
  },
  "usage": {
    "governed_runs": 123,
    "gateway_calls": 45,
    "metered_calls": 200,
    "active_workspaces": 3,
    "active_principals": 5
  },
  "features": ["agent.runtime", "knowledge.search", "mcp.basic", "plugin.basic", "workflow.runtime"]
}
```

| Field | What it is |
| ----- | ---------- |
| `installation_id` | A random UUID made the first time a report is built, stored in the database. It identifies nothing but this installation. |
| `version`, `edition` | The platform version, and `community` or `enterprise` as the license decides. |
| `day` | The UTC day the counts cover. |
| `deployment` | The `ENVIRONMENT`, `SOIT_ROLE`, `VECTOR_BACKEND` and `SECRETS_BACKEND` settings, and the scheme of `STORAGE_URL` (`file`, `s3`, ...), never the URL. |
| `usage.governed_runs` | Top-level runs started that day; a run started by another run counts once, with its parent. |
| `usage.gateway_calls` | Of those, runs that came through the gateway (`/v1`, `/mcp`, `/api/v1/tools`). |
| `usage.metered_calls` | Metered model and tool calls, from the daily usage aggregates. |
| `usage.active_workspaces`, `usage.active_principals` | How many workspaces and users or service principals had metered calls that day. |
| `features` | The enabled feature keys. |

A report carries no tenant, workspace, user, key or model names or ids, no
prompts or outputs, no addresses and no amounts. The receiving endpoint drops
the sender's IP address and keeps only the fields above.
