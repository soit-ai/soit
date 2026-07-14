"""Static guard for the persistence-free kernel contract region."""

from __future__ import annotations

import ast
from pathlib import Path


def test_kernel_contracts_do_not_import_framework_or_orm_packages() -> None:
    root = Path(__file__).parents[2] / "app" / "kernel" / "contracts"
    forbidden = ("fastapi", "sqlalchemy", "sqlmodel")
    violations: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.startswith(forbidden):
                    violations.append(f"{path.relative_to(root)}:{node.lineno} -> {name}")

    assert violations == []
