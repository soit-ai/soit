# SOIT Migration Runbook

## Supported Paths

Every release supports two PostgreSQL schema paths, and its notes under
[`docs/releases/`](releases/) name the exact revisions:

- **Fresh Installation**: an empty database upgrades from `base` through the
  explicit schema baseline `20260718140000` to the release's head.
- **N-1 Upgrade**: a database inside the release's supported range upgrades
  in place to its head.

For v1.8.0 the head is `20261003110000` and the supported N-1 upgrade range is
`20260927160000..20261003110000`, so a database written by v1.2.0 or any later
release upgrades in place. A database from an older release steps through the
intermediate releases in order, upgrading to each one's head before moving to
the next, as [versioning](versioning.md) describes.

Unknown development snapshots and skipped revisions are not supported. Back up
the database and object storage before an upgrade
([backup and restore runbook](operations/backup-restore.md)). Do not delete
`docker/data/` or another persistent data directory as a recovery shortcut.

## Revision Contract

Run from `server/`:

```bash
uv sync
uv run alembic heads
uv run alembic history --verbose
```

Expected output:

- `uv run alembic heads` reports exactly one revision, the head named in the
  release notes. CI fails when the chain has more than one head.
- `20260718140000` is the only root revision and contains an explicit,
  reviewable schema snapshot.
- The chain is linear, with each revision directly revising the one before it.
  The release notes describe every migration a release adds, together with
  its downgrade.

## Fresh Installation

Provision an empty PostgreSQL database, configure `DATABASE_URL`, and run:

```bash
uv run alembic upgrade head
uv run alembic current
uv run pytest tests/unit/test_fresh_install_migration.py -q
```

Required results:

- the upgrade runs every revision and exits successfully;
- `uv run alembic current` reports the head named in the release notes;
- the explicit-baseline contract test passes;
- the created table set matches current SQLModel metadata
  (`tests/postgres/test_migration_drift.py` checks this in CI).

Bootstrap only the operator account required for the target environment:

```bash
uv run python scripts/bootstrap_admin.py
```

The normal Community first-run workspace is intentionally usable without demo
seed data. Demo scenario scripts are optional acceptance fixtures, not a
runtime prerequisite.

The Docker Compose profiles run these steps for you: the `migrate` service
upgrades the database before the API and the workers start, and `bootstrap`
creates the operator account.

## N-1 Upgrade

First create recoverable backups and confirm the current revision lies inside
the release's supported range:

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

- the pre-upgrade revision lies inside the supported range;
- the upgrade exits successfully and current becomes the release's head;
- tenant, workspace, user, membership, Agent, Workflow, Knowledge, Run, outbox,
  and artifact sentinel data remain present;
- legacy `secret:*` references are converted to in-scope opaque Secret IDs;
- unresolved, malformed, cross-tenant, or cross-workspace secret references
  fail the migration instead of being silently retained.

Restart services only after the revision and preservation checks pass. Roll
back by restoring the pre-upgrade database and object-storage backups; do not
continue serving from a partially migrated database.

## Evidence Verification

Copy `docs/deployment/release-migration-evidence.example.json` to a local
evidence file, replace the example output with real fresh-install and N-1
results for the release, and validate it from `server/`:

```bash
uv run python scripts/verify_release_migration_paths.py ../docs/deployment/release-migration-evidence.json
```

The verifier requires one Alembic head, a fresh-install path that ends at that
head, an N-1 path from the stated source revision to it, schema checks,
preservation checks, smoke tests, and matching release-note ranges. The example
file records the v1.0.0 paths and shows the expected shape.

Local command output, operator notes, database dumps, and environment-specific
evidence belong outside the open-source repository.

## Failure Recovery

- Fresh installation: discard only the newly provisioned failed database and
  retry after fixing the cause.
- N-1 upgrade: keep services stopped and restore the captured database and
  object-storage backups as one consistent set.
- Do not downgrade a production database in place unless the release notes
  explicitly authorize and test that path.

## Exit Evidence

Before release, retain:

- `uv run alembic heads` and `uv run alembic history --verbose` output;
- fresh database upgrade, current-revision, and schema comparison output;
- N-1 source revision, upgrade, current revision, and sentinel preservation
  output;
- scoped Secret ID migration checks;
- smoke-test output;
- verifier output containing `"passed": true`.
