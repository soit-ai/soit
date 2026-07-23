# SOIT 1.0 Migration Runbook

## Supported Paths

SOIT 1.0 supports exactly two PostgreSQL schema paths:

- **Fresh Installation**: an empty database upgrades from `base` through the explicit schema baseline `20260718140000` to head `20260723160000`.
- **N-1 Upgrade**: a database at release-candidate revision `20260718140000` upgrades in place to `20260723160000`.

Databases older than `20260718140000`, unknown development snapshots, and skipped revisions are not supported. Back up the database and object storage before an N-1 upgrade. Do not delete `docker/data/` or another persistent data directory as a recovery shortcut.

## Revision Contract

Run from `server/`:

```bash
uv sync
uv run alembic heads
uv run alembic history --verbose
```

Expected output:

- `uv run alembic heads` reports `20260723160000 (head)`.
- `20260718140000` is the only root revision and contains an explicit, reviewable schema snapshot.
- `20260723160000` directly revises `20260718140000` and migrates legacy secret references to workspace-scoped opaque Secret IDs.
- `server/alembic/versions/` contains those two revisions only.

## Fresh Installation

Provision an empty PostgreSQL database, configure `DATABASE_URL`, and run:

```bash
uv run alembic upgrade head
uv run alembic current
uv run pytest tests/unit/test_fresh_install_migration.py -q
```

Required results:

- the upgrade runs both revisions and exits successfully;
- `uv run alembic current` reports `20260723160000 (head)`;
- the explicit-baseline contract test passes;
- the created table set matches current SQLModel metadata.

Bootstrap only the operator account required for the target environment:

```bash
uv run python scripts/bootstrap_admin.py
```

The normal Community first-run workspace is intentionally usable without demo seed data. Demo scenario scripts are optional acceptance fixtures, not a runtime prerequisite.

## N-1 Upgrade

The supported N-1 source is revision `20260718140000`. First create recoverable backups and confirm the current revision:

```bash
uv run alembic current
```

Stop API and worker processes that can write to the database, then run:

```bash
uv run alembic upgrade head
uv run alembic current
uv run pytest tests/unit/test_n1_migration_fixture.py tests/unit/test_scoped_secret_migration.py -q
```

Required results:

- the pre-upgrade revision is exactly `20260718140000`;
- the upgrade exits successfully and current becomes `20260723160000`;
- tenant, workspace, user, membership, Agent, Workflow, Knowledge, Run, outbox, and artifact sentinel data remain present;
- legacy `secret:*` references are converted to in-scope opaque Secret IDs;
- unresolved, malformed, cross-tenant, or cross-workspace secret references fail the migration instead of being silently retained.

Restart services only after the revision and preservation checks pass. Roll back by restoring the pre-upgrade database and object-storage backups; do not continue serving from a partially migrated database.

## Evidence Verification

Copy `docs/deployment/release-migration-evidence.example.json` to a local evidence file, replace example output with real fresh-install and N-1 results, and validate it from `server/`:

```bash
uv run python scripts/verify_release_migration_paths.py ../docs/deployment/release-migration-evidence.json
```

The verifier requires one Alembic head, the `base..20260723160000` fresh-install path, the `20260718140000..20260723160000` N-1 path, schema checks, preservation checks, smoke tests, and matching release-note ranges.

Local command output, operator notes, database dumps, and environment-specific evidence belong outside the open-source repository.

## Failure Recovery

- Fresh installation: discard only the newly provisioned failed database and retry after fixing the cause.
- N-1 upgrade: keep services stopped and restore the captured database and object-storage backups as one consistent set.
- Do not downgrade a production database in place unless the release notes explicitly authorize and test that path.

## Exit Evidence

Before release, retain:

- `uv run alembic heads` and `uv run alembic history --verbose` output;
- fresh database upgrade, current-revision, and schema comparison output;
- N-1 source revision, upgrade, current revision, and sentinel preservation output;
- scoped Secret ID migration checks;
- smoke-test output;
- verifier output containing `"passed": true`.
