# SOIT 1.0 Fresh Installation Migration Runbook

## Fresh Installation Only

SOIT 1.0 uses a single Alembic baseline and supports schema creation on an empty PostgreSQL database only. Upgrading a database created by an earlier development build is intentionally unsupported. Create a new database and reseed development data instead of reusing an old schema.

This policy applies to the database schema. Do not delete `docker/data/` or any other persistent data directory unless an operator has explicitly chosen to reset that environment.

## Single Baseline

Run from `server/`:

```bash
uv sync
uv run alembic heads
uv run alembic history --verbose
```

Expected output:

- `uv run alembic heads` reports `20260718140000 (head)`.
- Alembic history contains one revision whose parent is `<base>`.
- `server/alembic/versions/` contains only `20260718140000_fresh_install_baseline.py`.

## Empty PostgreSQL Database

Provision a database with no SOIT application tables, configure `DATABASE_URL`, and run:

```bash
uv run alembic upgrade head
uv run alembic current
uv run pytest tests/unit/test_fresh_install_migration.py -q
```

Required results:

- `uv run alembic upgrade head` exits successfully.
- `uv run alembic current` reports `20260718140000 (head)`.
- The fresh-install migration contract test passes.
- The created table set matches current SQLModel metadata.

After schema creation, bootstrap the required local data:

```bash
uv run python scripts/bootstrap_admin.py
uv run python scripts/bootstrap_enterprise_mvp.py
```

## Evidence Verification

Copy `docs/deployment/release-migration-evidence.example.json` to a local evidence file, replace example output with the fresh run, and validate it from `server/`:

```bash
uv run python scripts/verify_release_migration_paths.py ../docs/deployment/release-migration-evidence.json
```

The verifier requires one Alembic head, an empty starting database, a successful upgrade to the current baseline, schema checks, smoke tests, bootstrap commands, and a release-note range of `base..20260718140000`. It rejects the removed development-database upgrade path.

Local command output, operator notes, and environment-specific evidence belong outside the open-source repository.

## Failure Recovery

Because the supported target is a new database, recover by discarding only that newly provisioned failed database, fixing the installation, and retrying against another empty database. Do not point a failed partial installation at an existing SOIT database, and do not delete shared persistent directories as a shortcut.

## Exit Evidence

Before release, retain:

- `uv run alembic heads` and `uv run alembic history --verbose` output;
- fresh database `upgrade head` and `current` output;
- the passing fresh-install migration contract test;
- schema/table comparison output;
- bootstrap and smoke-test output;
- verifier output containing `"passed": true`.
