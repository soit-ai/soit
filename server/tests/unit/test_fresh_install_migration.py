"""Contracts for the explicit baseline and current migration chain."""

from __future__ import annotations

import importlib.util
import json
import re
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa

from alembic.migration import MigrationContext
from alembic.operations import Operations

SERVER_ROOT = Path(__file__).resolve().parents[2]
VERSIONS_ROOT = SERVER_ROOT / "alembic" / "versions"
BASELINE_PATH = VERSIONS_ROOT / "20260718140000_fresh_install_baseline.py"
SCOPED_SECRET_PATH = VERSIONS_ROOT / "20260723160000_scoped_secret_ids.py"
RUN_COST_PRICING_PATH = (
    VERSIONS_ROOT / "20260726190000_run_cost_pricing_snapshot.py"
)
INGEST_LEASE_PATH = (
    VERSIONS_ROOT / "20260728120000_knowledge_ingest_task_lease.py"
)
COST_DIMENSIONS_PATH = (
    VERSIONS_ROOT / "20260728150000_run_cost_dimension_columns.py"
)
BILLING_SEMANTICS_PATH = (
    VERSIONS_ROOT / "20260728160000_run_cost_billing_semantics.py"
)
DROP_ENTRY_TYPE_PATH = (
    VERSIONS_ROOT / "20260728180000_drop_run_cost_entry_type.py"
)
CREDIT_LEDGER_PATH = (
    VERSIONS_ROOT / "20260728200000_credit_ledger.py"
)
WORKFLOW_RUN_LEASE_PATH = (
    VERSIONS_ROOT / "20260728220000_workflow_run_lease.py"
)
API_KEY_SCOPES_PATH = (
    VERSIONS_ROOT / "20260728230000_api_key_scopes_and_expiry.py"
)
RUN_SANDBOX_PATH = (
    VERSIONS_ROOT / "20260728240000_run_sandbox_flag.py"
)
REGRESSION_DATASETS_PATH = (
    VERSIONS_ROOT / "20260731100000_regression_datasets_and_baselines.py"
)
REGRESSION_ANNOTATIONS_PATH = (
    VERSIONS_ROOT / "20260803090000_regression_annotations.py"
)
PRE_BASELINE_REPAIR_PATH = (
    VERSIONS_ROOT / "20260806160000_repair_pre_baseline_schema.py"
)
USER_SESSIONS_PATH = VERSIONS_ROOT / "20260830120000_user_sessions.py"
PREFERENCES_PATH = VERSIONS_ROOT / "20260830130000_saved_views_and_pins.py"
USER_MFA_PATH = VERSIONS_ROOT / "20260830140000_user_mfa.py"
WORKSPACE_MFA_PATH = VERSIONS_ROOT / "20260830150000_workspace_require_mfa.py"
ACCOUNT_DELETION_PATH = VERSIONS_ROOT / "20260830160000_account_deletion_requests.py"
SNAPSHOT_PATH = SERVER_ROOT / "alembic" / "schema" / "20260718140000.json"
N1_SOURCE_COMMIT = "5cbdec2946d22c98dd364fc535007e55dcfe1580"


def _load_baseline():
    spec = importlib.util.spec_from_file_location(
        "fresh_install_baseline", BASELINE_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_run_cost_pricing_migration():
    spec = importlib.util.spec_from_file_location(
        "run_cost_pricing_snapshot", RUN_COST_PRICING_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_cost_dimensions_migration():
    spec = importlib.util.spec_from_file_location(
        "run_cost_dimension_columns", COST_DIMENSIONS_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fresh_install_has_one_root_revision() -> None:
    assert sorted(path.name for path in VERSIONS_ROOT.glob("*.py")) == [
        BASELINE_PATH.name,
        SCOPED_SECRET_PATH.name,
        RUN_COST_PRICING_PATH.name,
        INGEST_LEASE_PATH.name,
        COST_DIMENSIONS_PATH.name,
        BILLING_SEMANTICS_PATH.name,
        DROP_ENTRY_TYPE_PATH.name,
        CREDIT_LEDGER_PATH.name,
        WORKFLOW_RUN_LEASE_PATH.name,
        API_KEY_SCOPES_PATH.name,
        RUN_SANDBOX_PATH.name,
        REGRESSION_DATASETS_PATH.name,
        REGRESSION_ANNOTATIONS_PATH.name,
        PRE_BASELINE_REPAIR_PATH.name,
        USER_SESSIONS_PATH.name,
        PREFERENCES_PATH.name,
        USER_MFA_PATH.name,
        WORKSPACE_MFA_PATH.name,
        ACCOUNT_DELETION_PATH.name,
    ]

    module = _load_baseline()
    assert module.revision == "20260718140000"
    assert module.down_revision is None

    spec = importlib.util.spec_from_file_location(
        "scoped_secret_ids", SCOPED_SECRET_PATH
    )
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == module.revision

    pricing_migration = _load_run_cost_pricing_migration()
    assert pricing_migration.down_revision == migration.revision

    lease_spec = importlib.util.spec_from_file_location(
        "knowledge_ingest_task_lease", INGEST_LEASE_PATH
    )
    assert lease_spec and lease_spec.loader
    lease_migration = importlib.util.module_from_spec(lease_spec)
    lease_spec.loader.exec_module(lease_migration)
    assert lease_migration.down_revision == pricing_migration.revision

    dimensions_migration = _load_cost_dimensions_migration()
    assert dimensions_migration.down_revision == lease_migration.revision

    semantics_spec = importlib.util.spec_from_file_location(
        "run_cost_billing_semantics", BILLING_SEMANTICS_PATH
    )
    assert semantics_spec and semantics_spec.loader
    semantics_migration = importlib.util.module_from_spec(semantics_spec)
    semantics_spec.loader.exec_module(semantics_migration)
    assert semantics_migration.down_revision == dimensions_migration.revision

    drop_spec = importlib.util.spec_from_file_location(
        "drop_run_cost_entry_type", DROP_ENTRY_TYPE_PATH
    )
    assert drop_spec and drop_spec.loader
    drop_migration = importlib.util.module_from_spec(drop_spec)
    drop_spec.loader.exec_module(drop_migration)
    assert drop_migration.down_revision == semantics_migration.revision

    ledger_spec = importlib.util.spec_from_file_location(
        "credit_ledger", CREDIT_LEDGER_PATH
    )
    assert ledger_spec and ledger_spec.loader
    ledger_migration = importlib.util.module_from_spec(ledger_spec)
    ledger_spec.loader.exec_module(ledger_migration)
    assert ledger_migration.down_revision == drop_migration.revision

    workflow_lease_spec = importlib.util.spec_from_file_location(
        "workflow_run_lease", WORKFLOW_RUN_LEASE_PATH
    )
    assert workflow_lease_spec and workflow_lease_spec.loader
    workflow_lease_migration = importlib.util.module_from_spec(workflow_lease_spec)
    workflow_lease_spec.loader.exec_module(workflow_lease_migration)
    assert workflow_lease_migration.down_revision == ledger_migration.revision

    api_key_spec = importlib.util.spec_from_file_location(
        "api_key_scopes_and_expiry", API_KEY_SCOPES_PATH
    )
    assert api_key_spec and api_key_spec.loader
    api_key_migration = importlib.util.module_from_spec(api_key_spec)
    api_key_spec.loader.exec_module(api_key_migration)
    assert api_key_migration.down_revision == workflow_lease_migration.revision

    sandbox_spec = importlib.util.spec_from_file_location(
        "run_sandbox_flag", RUN_SANDBOX_PATH
    )
    assert sandbox_spec and sandbox_spec.loader
    sandbox_migration = importlib.util.module_from_spec(sandbox_spec)
    sandbox_spec.loader.exec_module(sandbox_migration)
    assert sandbox_migration.down_revision == api_key_migration.revision

    regression_spec = importlib.util.spec_from_file_location(
        "regression_datasets_and_baselines", REGRESSION_DATASETS_PATH
    )
    assert regression_spec and regression_spec.loader
    regression_migration = importlib.util.module_from_spec(regression_spec)
    regression_spec.loader.exec_module(regression_migration)
    assert regression_migration.down_revision == sandbox_migration.revision

    annotations_spec = importlib.util.spec_from_file_location(
        "regression_annotations", REGRESSION_ANNOTATIONS_PATH
    )
    assert annotations_spec and annotations_spec.loader
    annotations_migration = importlib.util.module_from_spec(annotations_spec)
    annotations_spec.loader.exec_module(annotations_migration)
    assert annotations_migration.down_revision == regression_migration.revision

    repair_spec = importlib.util.spec_from_file_location(
        "repair_pre_baseline_schema", PRE_BASELINE_REPAIR_PATH
    )
    assert repair_spec and repair_spec.loader
    repair_migration = importlib.util.module_from_spec(repair_spec)
    repair_spec.loader.exec_module(repair_migration)
    assert repair_migration.down_revision == annotations_migration.revision


def test_run_cost_pricing_migration_merges_legacy_charge_rows(monkeypatch) -> None:
    migration = _load_run_cost_pricing_migration()
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    table = sa.Table(
        "run_cost_entries",
        metadata,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("step_id", sa.String()),
        sa.Column("entry_type", sa.String(), nullable=False),
        sa.Column("currency", sa.String()),
        sa.Column("amount", sa.Numeric(18, 6)),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("provider", sa.String()),
        sa.Column("provider_id", sa.String()),
        sa.Column("provider_slug", sa.String()),
        sa.Column("provider_kind", sa.String()),
        sa.Column("model_ref", sa.String()),
        sa.Column("upstream_model", sa.String()),
        sa.Column("tool_ref", sa.String()),
        sa.Column("prompt_tokens", sa.Integer()),
        sa.Column("completion_tokens", sa.Integer()),
        sa.Column("total_tokens", sa.Integer()),
    )
    metadata.create_all(engine)

    common = {
        "run_id": "run_legacy",
        "step_id": "step_legacy",
        "provider": "openai",
        "provider_id": "provider_legacy",
        "provider_slug": "openai-main",
        "provider_kind": "openai",
        "model_ref": "model:openai-main:gpt-4.1",
        "upstream_model": "gpt-4.1",
        "tool_ref": None,
    }
    with engine.begin() as connection:
        connection.execute(
            table.insert(),
            [
                {
                    **common,
                    "id": "usage_legacy",
                    "entry_type": "usage",
                    "currency": None,
                    "amount": None,
                    "unit": "tokens",
                    "quantity": 10,
                    "prompt_tokens": 6,
                    "completion_tokens": 4,
                    "total_tokens": 10,
                },
                {
                    **common,
                    "id": "charge_legacy",
                    "entry_type": "charge",
                    "currency": "USD",
                    "amount": Decimal("0.25"),
                    "unit": "tokens",
                    "quantity": 10,
                    "prompt_tokens": 6,
                    "completion_tokens": 4,
                    "total_tokens": 10,
                },
                {
                    **common,
                    "id": "latency_legacy",
                    "entry_type": "usage",
                    "currency": None,
                    "amount": None,
                    "unit": "ms",
                    "quantity": 25,
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "total_tokens": None,
                },
                {
                    **common,
                    "id": "orphan_charge",
                    "run_id": "run_orphan",
                    "step_id": "step_orphan",
                    "entry_type": "charge",
                    "currency": "USD",
                    "amount": Decimal("0.10"),
                    "unit": "tokens",
                    "quantity": 2,
                    "prompt_tokens": 2,
                    "completion_tokens": 0,
                    "total_tokens": 2,
                },
            ],
        )
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(migration, "op", operations)
        migration.upgrade()

        migrated = sa.Table(
            "run_cost_entries",
            sa.MetaData(),
            autoload_with=connection,
        )
        rows = {
            row["id"]: row
            for row in connection.execute(sa.select(migrated)).mappings()
        }

    assert set(rows) == {"usage_legacy", "latency_legacy", "orphan_charge"}
    usage = rows["usage_legacy"]
    assert usage["entry_type"] == "usage"
    assert usage["currency"] == "USD"
    assert usage["amount"] == Decimal("0.250000")
    assert usage["prompt_tokens"] == 6
    assert usage["pricing_snapshot_json"]["migration_action"] == "usage_charge_merged"
    assert usage["pricing_snapshot_json"]["configured_pricing"] == {}
    orphan = rows["orphan_charge"]
    assert orphan["entry_type"] == "usage"
    assert orphan["pricing_snapshot_json"]["migration_action"] == "orphan_charge_converted"


def test_run_cost_dimension_migration_merges_ms_rows_and_backfills(monkeypatch) -> None:
    migration = _load_cost_dimensions_migration()
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    table = sa.Table(
        "run_cost_entries",
        metadata,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("step_id", sa.String()),
        sa.Column("entry_type", sa.String(), nullable=False),
        sa.Column("currency", sa.String()),
        sa.Column("amount", sa.Numeric(18, 6)),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("provider", sa.String()),
        sa.Column("provider_id", sa.String()),
        sa.Column("provider_slug", sa.String()),
        sa.Column("provider_kind", sa.String()),
        sa.Column("model_ref", sa.String()),
        sa.Column("upstream_model", sa.String()),
        sa.Column("tool_ref", sa.String()),
        sa.Column("prompt_tokens", sa.Integer()),
        sa.Column("completion_tokens", sa.Integer()),
        sa.Column("total_tokens", sa.Integer()),
        sa.Column("pricing_snapshot_json", sa.JSON(), nullable=False),
    )
    metadata.create_all(engine)

    common = {
        "entry_type": "usage",
        "currency": None,
        "amount": None,
        "provider": None,
        "provider_id": None,
        "provider_slug": None,
        "provider_kind": None,
        "model_ref": None,
        "upstream_model": None,
        "tool_ref": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "pricing_snapshot_json": {},
    }
    with engine.begin() as connection:
        connection.execute(
            table.insert(),
            [
                {
                    **common,
                    "id": "tokens_row",
                    "run_id": "run_a",
                    "step_id": "step_a",
                    "unit": "tokens",
                    "quantity": 10,
                    "prompt_tokens": 6,
                    "completion_tokens": 4,
                    "total_tokens": 10,
                },
                {
                    **common,
                    "id": "ms_row",
                    "run_id": "run_a",
                    "step_id": "step_a",
                    "unit": "ms",
                    "quantity": 25,
                },
                {
                    **common,
                    "id": "orphan_ms_row",
                    "run_id": "run_a",
                    "step_id": "step_b",
                    "unit": "ms",
                    "quantity": 40,
                },
                {
                    **common,
                    "id": "vector_row",
                    "run_id": "run_a",
                    "step_id": "step_c",
                    "unit": "vectors",
                    "quantity": 7,
                    "provider": "vector",
                },
                {
                    **common,
                    "id": "tool_request_row",
                    "run_id": "run_a",
                    "step_id": "step_d",
                    "unit": "requests",
                    "quantity": 1,
                    "provider": "http",
                    "tool_ref": "tool:web.search",
                },
            ],
        )
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(migration, "op", operations)
        migration.upgrade()

        migrated = sa.Table(
            "run_cost_entries",
            sa.MetaData(),
            autoload_with=connection,
        )
        rows = {
            row["id"]: row
            for row in connection.execute(sa.select(migrated)).mappings()
        }

    assert set(rows) == {"tokens_row", "orphan_ms_row", "vector_row", "tool_request_row"}
    tokens_row = rows["tokens_row"]
    assert tokens_row["latency_ms"] == 25
    assert tokens_row["source_port"] == "llm"
    orphan = rows["orphan_ms_row"]
    assert orphan["latency_ms"] == 40
    assert orphan["unit"] == "ms"
    vector_row = rows["vector_row"]
    assert vector_row["vector_count"] == 7
    assert vector_row["source_port"] == "vector"
    tool_row = rows["tool_request_row"]
    assert tool_row["request_count"] == 1
    assert tool_row["source_port"] == "tools"


def test_fresh_install_baseline_is_an_explicit_n1_schema_snapshot() -> None:
    source = BASELINE_PATH.read_text(encoding="utf-8")
    assert SNAPSHOT_PATH.is_file()
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    assert snapshot["format"] == "soit-schema-snapshot-v1"
    assert snapshot["revision"] == "20260718140000"
    assert snapshot["source_commit"] == N1_SOURCE_COMMIT
    assert len(snapshot["tables"]) == 58
    created_tables = set(re.findall(r'op\.create_table\(\s*["\']([^"\']+)', source))
    assert created_tables == set(snapshot["tables"])
    assert "SQLModel.metadata" not in source
    assert ".create_all(" not in source
    assert ".drop_all(" not in source
    assert re.search(
        r'sa\.PrimaryKeyConstraint\(\s*"tenant_id",\s*"user_id",\s*name="uq_tenant_membership"',
        source,
    )
    assert re.search(
        r'sa\.PrimaryKeyConstraint\(\s*"tenant_id",\s*"workspace_id",\s*"user_id",\s*name="uq_workspace_membership"',
        source,
    )
    assert not re.search(r'sa\.UniqueConstraint\([^)]*name="uq_(tenant|workspace)_membership"', source)


def test_fresh_install_snapshot_includes_required_n1_tables() -> None:
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    assert {
        "attachments",
        "product_feedbacks",
        "response_interactions",
        "run_step_tool_calls",
        "workflow_runs",
    } <= set(snapshot["tables"])
    assert {"apps", "app_versions", "app_publishes"}.isdisjoint(snapshot["tables"])


def test_fresh_install_baseline_creates_and_drops_explicit_tables(monkeypatch) -> None:
    module = _load_baseline()
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    created: list[str] = []
    dropped: list[str] = []

    monkeypatch.setattr(module.op, "f", lambda name: name)
    monkeypatch.setattr(
        module.op, "create_table", lambda name, *args, **kwargs: created.append(name)
    )
    monkeypatch.setattr(module.op, "create_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.op, "drop_index", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        module.op, "drop_table", lambda name, *args, **kwargs: dropped.append(name)
    )

    module.upgrade()
    module.downgrade()

    assert created == snapshot["tables"]
    assert dropped == list(reversed(snapshot["tables"]))
