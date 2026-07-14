"""Architecture tests for kernel import boundaries."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

KERNEL_ROOT = Path(__file__).resolve().parents[2] / "app" / "kernel"
APP_ROOT = Path(__file__).resolve().parents[2] / "app"
SERVER_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = SERVER_ROOT.parent
RUNTIME_DB_MODELS_ROOT = KERNEL_ROOT / "runtime" / "db" / "models"
FORBIDDEN_PREFIXES = (
    "app.modules",
    "app.api",
    "app.adapters",
    "app.infra",
)


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
    return modules


def test_kernel_does_not_import_outer_application_layers():
    violations: list[str] = []
    for path in sorted(KERNEL_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        for module in _imported_modules(path):
            if module.startswith(FORBIDDEN_PREFIXES):
                rel = path.relative_to(KERNEL_ROOT.parents[1])
                violations.append(f"{rel}: {module}")

    assert violations == []


def _called_functions(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.append(func.id)
            elif isinstance(func, ast.Attribute):
                calls.append(func.attr)
    return calls


def test_kernel_provider_registration_only_happens_in_wiring():
    provider_register_calls = {
        "register_resource_grant_provider",
        "register_egress_scope_policy_provider",
    }
    violations: list[str] = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(APP_ROOT)
        if rel.parts and rel.parts[0] == "wiring":
            continue
        calls = set(_called_functions(path))
        used = sorted(provider_register_calls.intersection(calls))
        if used:
            violations.append(f"{rel}: {', '.join(used)}")

    assert violations == []


def test_kernel_db_table_models_only_live_under_runtime_db_models():
    violations: list[str] = []
    for path in sorted(KERNEL_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        has_table_model = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            inherits_sqlmodel = any(
                isinstance(base, ast.Name) and base.id == "SQLModel"
                for base in node.bases
            )
            has_table_true = any(
                isinstance(keyword.value, ast.Constant)
                and keyword.arg == "table"
                and keyword.value.value is True
                for keyword in node.keywords
            )
            if inherits_sqlmodel and has_table_true:
                has_table_model = True
                break
        if has_table_model and not path.is_relative_to(RUNTIME_DB_MODELS_ROOT):
            violations.append(str(path.relative_to(SERVER_ROOT)))

    assert violations == []


def test_old_kernel_runtime_import_paths_are_removed():
    forbidden_imports = (
        "app.kernel." + "trace",
        "app.kernel." + "responses",
        "app.kernel.audit." + "models",
        "app.kernel.events." + "outbox_models",
        "app.kernel.observe." + "idempotency",
        "app.kernel.runtime." + "core",
        "app.kernel.runtime." + "models",
        "app.kernel.runtime." + "repository",
        "app.kernel.runtime." + "schemas",
        "app.kernel.runtime." + "query_service",
        "app.kernel.runtime." + "events",
        "app.kernel.runtime." + "outbox_emit",
        "app.kernel.runtime.contracts." + "status",
        "app.kernel.runtime." + "handlers",
    )
    violations: list[str] = []
    for path in sorted(SERVER_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts or ".venv" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for item in forbidden_imports:
            if item in text:
                violations.append(f"{path.relative_to(SERVER_ROOT)}: {item}")

    assert violations == []


def test_old_kernel_runtime_import_scan_ignores_virtualenv(
    monkeypatch,
    tmp_path: Path,
):
    ignored_file = tmp_path / ".venv" / "lib" / "legacy.py"
    ignored_file.parent.mkdir(parents=True)
    ignored_file.write_text(
        "import app.kernel." + "trace\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "SERVER_ROOT", tmp_path)

    test_old_kernel_runtime_import_paths_are_removed()


def test_old_kernel_runtime_files_are_removed():
    old_paths = [
        KERNEL_ROOT / "trace",
        KERNEL_ROOT / "responses",
        KERNEL_ROOT / "runtime" / "core",
        KERNEL_ROOT / "runtime" / "contracts",
        KERNEL_ROOT / "runtime" / "models.py",
        KERNEL_ROOT / "runtime" / "repository.py",
        KERNEL_ROOT / "runtime" / "schemas.py",
        KERNEL_ROOT / "runtime" / "query_service.py",
        KERNEL_ROOT / "events" / "outbox_models.py",
        KERNEL_ROOT / "observe" / "idempotency.py",
    ]

    assert [str(path.relative_to(SERVER_ROOT)) for path in old_paths if path.exists()] == []


def test_docs_do_not_reference_removed_kernel_runtime_paths():
    forbidden_doc_refs = (
        "app/kernel/" + "trace",
        "server/app/kernel/" + "trace",
        "app.kernel." + "trace",
        "kernel." + "trace",
        "app/kernel/" + "responses",
        "server/app/kernel/" + "responses",
        "app.kernel." + "responses",
        "kernel." + "responses",
        "kernel/runtime/" + "core",
        "server/app/kernel/runtime/" + "core",
        "kernel/runtime/" + "contracts/status",
        "app.kernel.runtime.contracts." + "status",
        "kernel/runtime/" + "models",
        "kernel/runtime/" + "repository",
        "kernel/runtime/" + "schemas",
        "kernel/runtime/" + "query_service",
        "events/" + "outbox_models.py",
        "observe/" + "idempotency.py",
    )
    doc_roots = [
        REPO_ROOT / "docs",
        SERVER_ROOT / "docs",
        KERNEL_ROOT,
    ]
    violations: list[str] = []
    for root in doc_roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for item in forbidden_doc_refs:
                if item in text:
                    violations.append(f"{path.relative_to(REPO_ROOT)}: {item}")

    assert violations == []
