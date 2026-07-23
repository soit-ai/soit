# SOIT Community Backup and Restore Runbook

This runbook covers recoverable Community data for the reference Docker Compose
topology. It is a portability and release-rollback procedure, not the Enterprise
`deployment.backup_restore` feature, managed scheduling, high availability, or a
disaster-recovery service.

## Recovery Objectives and Data Model

Choose explicit targets before operating a deployment. The reference drill uses
an RPO of 60 minutes and an RTO of 240 minutes; production owners must select and
test targets appropriate to their workload.

The canonical recovery set is:

- PostgreSQL custom-format dump, including application state, Alembic revision,
  run evidence, Knowledge metadata, and Secret metadata;
- object storage mirror, including uploaded source documents and run artifacts.

The vector index is derived data. Restore PostgreSQL and object storage first,
then rebuild every active Knowledge vector index and prove query/citation
readback. Secret metadata is restored from PostgreSQL, but secret values are not
included in Community backup artifacts. Reconnect the external secret store or
rotate values before starting workers.

The Quickstart Vault dev mode is in-memory and is intentionally not recoverable.
It must never be used as a production secret store. A restore that only recovers
Secret metadata while leaving missing values unresolved is incomplete.

Redis is treated as an ephemeral coordination/cache layer. Do not restore stale
leases or cached authorization decisions; start it empty after canonical data is
restored.

## Create a Consistent Backup

1. Record the deployment, release version, current Alembic revision, backup ID,
   operator, start time, RPO, and RTO.
2. Stop `web`, `api`, `knowledge-ingest-worker`, and `outbox-dispatcher`. Keep
   PostgreSQL and MinIO reachable. Confirm no ingest or outbox work is still
   running.
3. Create a custom-format PostgreSQL dump with `pg_dump --format=custom
   --no-owner --no-acl`.
4. Mirror the configured application bucket to a new, empty backup directory.
5. Generate SHA-256 and byte-size records for the dump, Alembic revision file,
   and every object-storage file. Do not put secret values in the backup or logs.
6. Create a manifest matching
   `docs/deployment/backup-manifest.example.json`, then verify both structure and
   local files:

The reference tool performs steps 2–6, refuses a non-empty destination, and
refuses to run while application services are active. Choose a destination
outside the Git checkout:

```powershell
python docker/operations/compose_backup.py `
  --project-name soit `
  --output F:\soit-backups\backup-20260723
```

The default `--minio-endpoint http://minio:9000` assumes the current Compose
network. For an externally managed endpoint, pass an address reachable from the
temporary `mc` container and provide credentials through environment variables,
not command-line arguments.

```powershell
cd server
uv run python scripts/verify_backup_manifest.py `
  ../artifacts/backup/backup-manifest.json `
  --backup-root ../artifacts/backup
```

Write backup artifacts outside the Git checkout and copy them to access-controlled,
encrypted storage. A manifest or checksum without the corresponding protected
data is not a backup.

## Restore into an Isolated Target

Never test a restore over the only copy of a deployment. Resolve and record the
target database and bucket before any destructive command.

1. Create an isolated PostgreSQL database, object-storage bucket, Milvus
   namespace/collection set, and secret-store namespace.
   The Compose profile exposes `DATABASE_PUBLISHED_PORT`,
   `MINIO_API_PUBLISHED_PORT`, and `MINIO_CONSOLE_PUBLISHED_PORT` specifically so
   a restore-drill project can run alongside the source without port collisions.
2. Verify the backup manifest and every local checksum before changing the target.
3. Keep all application processes stopped. Restore the PostgreSQL dump with
   `pg_restore --clean --if-exists --no-owner --no-acl` into the isolated target.
4. Restore the object mirror into the isolated bucket and compare every object
   size and SHA-256 with the manifest.
5. Run `alembic current`, compare canonical table row counts, and read back a
   sample of run evidence, documents, attachments, and Secret metadata.
6. Reconnect or rotate every referenced secret value. The Quickstart Vault dev
   mode cannot supply recovered values.
7. Start Milvus, then the API, and invoke the real Knowledge index rebuild action
   for every active index. A collection existing is insufficient: run a retrieval
   query and validate its citations.
8. Start `knowledge-ingest-worker` and `outbox-dispatcher`, then `web`. Confirm API,
   worker, and dispatcher readiness.
9. Run the empty-workspace release journey and record evidence without editing the
   database directly.
10. Fill `docs/deployment/restore-drill-evidence.example.json` with real paths,
    times, RPO/RTO, readbacks, and rollback evidence, then verify it:

The reference restore tool replaces only the confirmed PostgreSQL database and
application bucket. It requires the exact Compose project, database, and bucket
names to be repeated and refuses to run while application services are active:

```powershell
python docker/operations/compose_restore.py `
  --backup-root F:\soit-backups\backup-20260723 `
  --project-name soit-restore-drill `
  --confirm-project soit-restore-drill `
  --confirm-database soit_restore_drill `
  --confirm-bucket soit-restore-drill-artifacts
```

This command intentionally does not claim a complete restore. Secret value
reconnection, vector index rebuild/query readback, smoke tests, and rollback must
still be completed and recorded.

```powershell
cd server
uv run python scripts/verify_restore_drill.py `
  ../artifacts/restore-drill/restore-drill-evidence.json
```

Local outputs, screenshots, database dumps, and environment-specific evidence
belong outside the Community repository.

## Rollback

For a failed N-1 upgrade, stop all application processes and restore PostgreSQL
and object storage from the same backup ID. Never combine a database from one
backup point with objects from another. Reconnect secrets, rebuild vector indexes,
run readbacks, and only then resume traffic. If the old application cannot safely
read the restored schema, keep traffic stopped and escalate; repeated downgrade or
partial migration attempts are not a rollback strategy.

Record actual RPO and RTO from timestamps. A drill passes only when PostgreSQL,
object storage, vector query/citation readback, Secret metadata/value reconnection,
workers, outbox, product smoke tests, and the rollback path all pass.
