"""Contract tests for the fresh-install-only Alembic baseline."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[2]
VERSIONS_ROOT = SERVER_ROOT / "alembic" / "versions"
BASELINE_PATH = VERSIONS_ROOT / "20260718140000_fresh_install_baseline.py"


def _load_baseline():
    spec = importlib.util.spec_from_file_location("fresh_install_baseline", BASELINE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fresh_install_has_one_root_revision() -> None:
    assert sorted(path.name for path in VERSIONS_ROOT.glob("*.py")) == [BASELINE_PATH.name]

    module = _load_baseline()
    assert module.revision == "20260718140000"
    assert module.down_revision is None


def test_fresh_install_baseline_registers_the_current_schema() -> None:
    module = _load_baseline()
    current_tables = set(module.SQLModel.metadata.tables)

    assert {
        "attachments",
        "product_feedbacks",
        "response_interactions",
        "run_step_tool_calls",
        "workflow_runs",
    } <= current_tables
    assert {"apps", "app_versions", "app_publishes"}.isdisjoint(current_tables)


def test_fresh_install_baseline_creates_and_drops_metadata(monkeypatch) -> None:
    module = _load_baseline()
    bind = object()
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    monkeypatch.setattr(
        module.SQLModel.metadata,
        "create_all",
        lambda *, bind: calls.append(("create", bind)),
    )
    monkeypatch.setattr(
        module.SQLModel.metadata,
        "drop_all",
        lambda *, bind: calls.append(("drop", bind)),
    )

    module.upgrade()
    module.downgrade()

    assert calls == [("create", bind), ("drop", bind)]
