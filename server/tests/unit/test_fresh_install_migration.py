"""Contract tests for the fresh-install-only Alembic baseline."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[2]
VERSIONS_ROOT = SERVER_ROOT / "alembic" / "versions"
BASELINE_PATH = VERSIONS_ROOT / "20260718140000_fresh_install_baseline.py"
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


def test_fresh_install_has_one_root_revision() -> None:
    assert sorted(path.name for path in VERSIONS_ROOT.glob("*.py")) == [
        BASELINE_PATH.name
    ]

    module = _load_baseline()
    assert module.revision == "20260718140000"
    assert module.down_revision is None


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
