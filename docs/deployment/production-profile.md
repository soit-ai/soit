# Hardened Production Profile

The reference lives in `docker/docker-compose.production.yml` with supporting
files in `docker/production/`. It is a starting point for an operator, not a
turnkey stack.

## What this profile is, and is not

It **is** the process topology the runtime requires, expressed so the settings
validator accepts it: TLS in front, the API never published directly, execution
outside the request, the outbox dispatcher and the knowledge ingest worker as
their own processes, plugin code signed and verifiable.

It is **not** a place to run your database. The file deliberately bundles no
PostgreSQL, Redis, object store, vector store or Vault. Running stateful
infrastructure as disposable sibling containers is what makes a "production"
compose file untrue; those belong to your platform, and this file only points at
them. `tests/unit/test_production_profile_contract.py` asserts none of them
reappear.

It is also **not** a high-availability or disaster-recovery design. It runs one
API service behind one gateway on one host. Multi-replica deployment, failover
and DR remain unaddressed; see the release checklist rather than assuming this
covers them.

## Required configuration

Every value below has no default. The compose file fails to render without
them, which is intended: a silent fallback here is a production incident later.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Managed PostgreSQL, with credentials and database name |
| `REDIS_URL`, `EVENT_BUS_REDIS_URL` | Cache and event bus |
| `SECRET_KEY` | At least 32 characters, not a placeholder |
| `VAULT_URL`, `VAULT_TOKEN` | A real Vault, not a dev-mode server |
| `STORAGE_OPTIONS_JSON` | Object storage endpoint and credentials, not the dev defaults |
| `MILVUS_HOST` | Vector store |
| `PLUGIN_SIGNATURE_PUBLIC_KEYS` | Keys trusted to sign plugin packages |
| `SOIT_PUBLIC_HOSTNAME` | Hostname the gateway obtains a certificate for |

A dev-mode Vault keeps its data in memory and unseals itself with a fixed root
token, so it loses every secret on restart. The profile cannot detect that for
you; point `VAULT_URL` at a real server.

`ACCESS_TOKEN_EXPIRE_MINUTES` (default 480) is the hard session length: there
is no token refresh flow yet, so users are logged out when it expires. Tighten
it if your threat model calls for shorter exposure windows.

## What the runtime refuses in production

`Settings.validate_runtime_requirements()` runs at startup and fails closed. In
production it requires an external database with credentials, the Redis event
bus, OpenTelemetry with an OTLP endpoint, Vault, a non-placeholder secret key,
at least one model provider key, plugin signature verification with at least one
trusted key, and plugin digest verification. It refuses inline chat execution,
an in-process outbox dispatcher, and content safety enabled without an endpoint.

It also refuses the object storage credentials shipped in `.env.example` and
MinIO's own stock defaults. `docker-compose.yml` uses those defaults for local
development, so copying a dev `STORAGE_OPTIONS_JSON` into production is the
mistake this check exists to stop. Omitting the credentials entirely is still
allowed: that means the backend supplies its own identity, such as an IAM role.

`test_the_api_service_satisfies_production_validation` derives settings from the
compose file and runs that same validation, so the shipped profile cannot drift
away from what the runtime demands.

## Deploy

```bash
docker compose -f docker/docker-compose.production.yml config --quiet
docker compose -f docker/docker-compose.production.yml up -d
```

`migrate` runs to completion before the API, dispatcher and worker start. See
[release-migration.md](../release-migration.md) for the supported upgrade paths;
back up the database and object storage before an N-1 upgrade.

## Observability

`docker/production/otel-collector.yaml` receives OTLP traces and forwards them
to your backend via `OTEL_TRACES_BACKEND_ENDPOINT`. It drops
`soit.input_summary`, `soit.output_summary` and `soit.tool.parameters` before
export: traces carry prompts and tool arguments, and those most often hold
customer data.

`docker/production/alerts.yaml` contains Prometheus rules for the failure modes
this runtime actually has — terminal outbox failures, a stalled dispatcher, a
retry storm, run failure ratio, P95 run duration, and runs that are active while
nothing completes (the signature of executions orphaned by a restart).
`test_every_alert_references_a_metric_the_runtime_exports` asserts every
expression names a metric the code emits; a rule referencing a metric that is
never emitted never fires, which reads as coverage while providing none.

Sampling defaults to `OTEL_TRACES_SAMPLE_RATIO=0.1`. Raise it while
investigating, and be aware of the cost at full sampling.

### Verifying redaction

Redaction is the one part of this config that is a promise about customer data,
so confirm it on the wire rather than trusting the file. Run the collector
pointed at an endpoint you control, send a span carrying the attributes that
should be dropped alongside one that should survive, and inspect what arrives.
The exporter gzips its payload, so decompress before searching — a plain search
of the raw bytes finds nothing and reads as a pass.

```bash
docker run --rm -p 14318:4318 \
  -v "$PWD/docker/production/otel-collector.yaml:/etc/otel/config.yaml:ro" \
  -e OTEL_TRACES_BACKEND_ENDPOINT="http://<your sink>" \
  otel/opentelemetry-collector-contrib:0.109.0 --config=/etc/otel/config.yaml
```

A correct result drops `soit.input_summary`, `soit.output_summary` and
`soit.tool.parameters` entirely — key and value — while `soit.run_id`, the
service name and the span name still arrive. Losing those too would mean the
traces are redacted into uselessness.

## Not covered here

- **Load and failure-injection baselines.** No numbers are published because
  none have been measured. `docs/deployment/load-baseline.md` describes the
  procedure; the figures must come from your own hardware.
- **High availability and disaster recovery.** Single-host, single-replica.
- **Log retention.** The collector handles traces only; ship container logs with
  your platform's mechanism and set retention to your compliance requirement.
