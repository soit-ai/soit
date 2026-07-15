# SOIT 1.0 Upgrade and Migration Runbook

Status: Phase 1 migration-documentation foundation. This runbook documents the required commands and evidence for the 1.0 release gate; it is not itself proof that both database paths have been executed.

## Preflight

Run from `server/`:

```bash
uv sync
uv run alembic heads
uv run alembic history --verbose
```

Expected before release:

- `uv run alembic heads` reports exactly one release head.
- The release candidate branch contains no unreviewed migration files.
- All migrations are committed and referenced in release notes.

## Backup

Before upgrading a development or customer-like database:

1. Export PostgreSQL with a timestamped dump.
2. Record current `alembic_version`.
3. Export `.env` or deployment environment settings.
4. Snapshot object storage, vector store, and Vault data when the environment contains demo or customer-like data.
5. Record the exact SOIT commit, Docker image tag, and operator.

## Empty Database Path

This path proves a fresh installation can initialize the schema from scratch.

```bash
cd server
uv run alembic upgrade head
uv run alembic current
uv run pytest tests/unit/test_runtime_db_models.py tests/unit/test_feature_entitlements.py -q
```

Required evidence:

- Database starts with no SOIT application tables.
- `uv run alembic upgrade head` exits 0.
- `uv run alembic current` shows the same revision as `uv run alembic heads`.
- Bootstrap and demo seed commands can run after migration:

```bash
uv run python scripts/bootstrap_admin.py
uv run python scripts/bootstrap_enterprise_mvp.py
```

## Development Database Path

This path proves an existing local development database can upgrade without destructive reset.

```bash
cd server
uv run alembic current
uv run alembic upgrade head
uv run alembic current
uv run pytest tests/integration/test_enterprise_agent_mvp.py -q
```

Required evidence:

- Pre-upgrade revision is recorded.
- Post-upgrade revision matches `head`.
- Existing tenant/workspace/user rows remain readable.
- Demo Chain A or Chain B still runs after migration.
- No manual `docker/data/` cleanup or destructive reset was used.

## Evidence Verification

Record the empty-database and development-database command output in the evidence format below:

```bash
docs/deployment/release-migration-evidence.example.json
```

Then verify it from `server/`:

```bash
uv run python scripts/verify_release_migration_paths.py ../docs/deployment/release-migration-evidence.example.json
```

Local migration drill records should be kept outside this open-source repository.

Generate a fresh release-specific evidence file before publishing an immutable release tag.

The verifier requires:

- exactly one Alembic head;
- empty-database migration output ending at the release head;
- development-database pre-upgrade and post-upgrade revisions, where the pre-upgrade revision must be before the release head;
- a backup timestamp, restore point, operator, and commit for the development database path;
- no destructive reset for the development database path;
- successful smoke/demo commands for both paths;
- release notes listing the migration range.

## Rollback

Alembic downgrade support is migration-specific and should not be assumed for customer data. The supported rollback plan for 1.0 release validation is:

1. Stop API, worker, and web processes.
2. Restore PostgreSQL from the pre-upgrade dump.
3. Restore object/vector/Vault snapshots when the failed migration touched related state.
4. Restore previous image tags or commit.
5. Run `uv run alembic current` and the relevant smoke test.

If a migration has a verified Alembic `downgrade()` path, it may be used only in a disposable staging environment before relying on it operationally.

## Exit Evidence

Do not check the roadmap migration item until these artifacts exist:

- `uv run alembic heads` output showing the release head.
- Empty Database Path command output.
- Development Database Path command output.
- Backup timestamp and restore point for the development database path.
- Smoke or integration test evidence after both paths.
- Release notes listing the migration range.
- `uv run python scripts/verify_release_migration_paths.py <release-evidence.json>` output showing `"passed": true`.
