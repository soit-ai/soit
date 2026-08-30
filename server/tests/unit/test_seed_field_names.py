"""Every seed script writes field names its model actually has.

A seed builds rows by keyword, so a wrong field name is not a type error. On the
insert path SQLModel accepts the extra key and simply drops it, which means the
column silently stays empty and the seed still reports success -- the failure
only surfaces on a re-seed, where the update path raises, or much later when a
page renders blank. Both of those happened while this seed was being written.

Checking the literal keys against ``model_fields`` catches the whole class in
one pass, without a database.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

SEED_MODULES = [
    "scripts.seed_console_prototype",
]


def _bad_field_names(module_name: str) -> list[str]:
    module = importlib.import_module(module_name)
    source = Path(module.__file__)
    tree = ast.parse(open(source, encoding="utf-8").read())

    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if called != "_upsert" or len(node.args) < 4:
            continue

        model_name = getattr(node.args[1], "id", None)
        if not model_name:
            continue
        model = getattr(module, model_name, None)
        if model is None:
            problems.append(
                f"line {node.lineno}: {model_name} is not imported in the seed"
            )
            continue

        fields = set(getattr(model, "model_fields", {}) or {})
        if not fields:
            continue

        values = node.args[3]
        if not isinstance(values, ast.Dict):
            continue
        for key in values.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                if key.value not in fields:
                    problems.append(
                        f"line {key.lineno}: {model_name} has no field {key.value!r}"
                    )
    return problems


@pytest.mark.parametrize("module_name", SEED_MODULES)
def test_seed_writes_only_real_model_fields(module_name: str) -> None:
    problems = _bad_field_names(module_name)
    assert not problems, "\n".join(problems)
