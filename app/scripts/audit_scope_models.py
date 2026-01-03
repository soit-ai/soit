"""audit_scope_models

CI/quality gate: ensure all SQLModel tables in app/modules (except identity) include tenant_id and workspace_id.

Rationale:
- Repository base applies scope only if fields exist.
- Missing fields can accidentally create cross-tenant visibility.

Usage:
    python scripts/audit_scope_models.py
"""

from __future__ import annotations

import ast
from pathlib import Path
import sys
from typing import List, Tuple


MODULES_DIR = Path(__file__).resolve().parents[1] / "app" / "modules"

# Only allow non-scoped tables inside identity domain (global identity/tenancy tables)
ALLOWLIST_PATH_PARTS = {
    str(Path("identity") / "domain" / "models.py"),
}


def _is_sqlmodel_table(node: ast.ClassDef) -> bool:
    # class X(SQLModel, table=True):
    for kw in getattr(node, "keywords", []) or []:
        if kw.arg == "table" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            return True
    return False


def _has_field(node: ast.ClassDef, name: str) -> bool:
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if stmt.target.id == name:
                return True
    return False


def audit() -> List[Tuple[str, str]]:
    issues: List[Tuple[str, str]] = []
    for py in MODULES_DIR.rglob("*.py"):
        rel = py.relative_to(MODULES_DIR)
        # only check domain model modules (most reliable)
        if rel.name != "models.py":
            continue
        rel_str = rel.as_posix()
        # allowlisted paths
        if any(rel_str.endswith(p.as_posix()) for p in [Path(x) for x in ALLOWLIST_PATH_PARTS]):
            continue

        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError as e:
            issues.append((rel_str, f"syntax error: {e}"))
            continue

        for node in tree.body:
            if isinstance(node, ast.ClassDef) and _is_sqlmodel_table(node):
                if not _has_field(node, "tenant_id") or not _has_field(node, "workspace_id"):
                    issues.append((rel_str, f"{node.name} missing tenant_id/workspace_id"))
    return issues


def main() -> int:
    issues = audit()
    if not issues:
        print("OK: all scoped tables include tenant_id/workspace_id")
        return 0

    print("FAILED: missing tenant/workspace scope on SQLModel tables:")
    for file, msg in issues:
        print(f" - {file}: {msg}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
