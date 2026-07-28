# SOIT 1.0 Migration Runbook

## Supported Paths

SOIT 1.0 supports exactly two PostgreSQL schema paths:

- **Fresh Installation**: an empty database upgrades from `base` through the explicit schema baseline `20260718140000` to head `20260728200000`.
- **N-1 Upgrade**: a database at release-candidate revision `20260718140000` upgrades in place to `20260728200000`.

Databases older than `20260718140000`, unknown development snapshots, and skipped revisions are not supported. Back up the database and object storage before an N-1 upgrade. Do not delete `docker/data/` or another persistent data directory as a recovery shortcut.

## Revision Contract

Run from `server/`:

```bash
uv sync
uv run alembic heads
uv run alembic history --verbose
```

Expected output:

- `uv run alembic heads` reports `20260728200000 (head)`.
- `20260718140000` is the only root revision and contains an explicit, reviewable schema snapshot.
- The chain is linear, with each revision directly revising the one above it:

| Revision | Change |
|---|---|
| `20260718140000` | Explicit fresh-install schema baseline (root). |
| `20260723160000` | Migrates legacy secret references to workspace-scoped opaque Secret IDs. |
| `20260726190000` | Merges historical usage/charge pairs into one usage row, converts orphan charge rows, and adds immutable pricing snapshots with honest legacy placeholders where the original pricing configuration cannot be reconstructed. |
| `20260728120000` | Adds execution leases to knowledge ingest tasks and expires the lease on already-running rows so tasks stranded by a crashed worker are reclaimed. |
| `20260728150000` | Adds dimension columns to `run_cost_entries` and merges latency rows so each metered invocation is one row. |
| `20260728160000` | Narrows billing semantics to `billing_basis`/`billed_quantity` and adds an idempotency key. |
| `20260728180000` | Drops `run_cost_entries.entry_type`, retiring the usage/charge split. |
| `20260728200000` | Creates `credit_ledger_entries` for credit deduction derived from priced usage. |

- `server/alembic/versions/` contains those eight revisions only.

## Fresh Installation

Provision an empty PostgreSQL database, configure `DATABASE_URL`, and run:

```bash
uv run alembic upgrade head
uv run alembic current
uv run pytest tests/unit/test_fresh_install_migration.py -q
```

Required results:

- the upgrade runs all eight revisions and exits successfully;
- `uv run alembic current` reports `20260728200000 (head)`;
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
- the upgrade exits successfully and current becomes `20260728200000`;
- tenant, workspace, user, membership, Agent, Workflow, Knowledge, Run, outbox, and artifact sentinel data remain present;
- legacy `secret:*` references are converted to in-scope opaque Secret IDs;
- unresolved, malformed, cross-tenant, or cross-workspace secret references fail the migration instead of being silently retained.

Restart services only after the revision and preservation checks pass. Roll back by restoring the pre-upgrade database and object-storage backups; do not continue serving from a partially migrated database.

## Evidence Verification

Copy `docs/deployment/release-migration-evidence.example.json` to a local evidence file, replace example output with real fresh-install and N-1 results, and validate it from `server/`:

```bash
uv run python scripts/verify_release_migration_paths.py ../docs/deployment/release-migration-evidence.json
```

The verifier requires one Alembic head, the `base..20260728200000` fresh-install path, the `20260718140000..20260728200000` N-1 path, schema checks, preservation checks, smoke tests, and matching release-note ranges.

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
