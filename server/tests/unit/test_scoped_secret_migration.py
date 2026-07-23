"""Data-contract tests for the scoped secret ID migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_migration_module():
    path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "20260723160000_scoped_secret_ids.py"
    )
    spec = importlib.util.spec_from_file_location("scoped_secret_ids_migration", path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load scoped secret migration")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_rewrites_nested_legacy_secret_fields_to_ids():
    migration = _load_migration_module()
    resolved: list[str] = []

    def resolve(value: str) -> str:
        resolved.append(value)
        return value.removeprefix("secret:")

    migrated = migration._migrate_payload(
        {
            "auth": {
                "secret_ref": "secret:sec_primary",
                "secret_refs": ["secret:sec_primary", "sec_secondary"],
                "secret_bindings": {"api_key": "secret:sec_primary"},
            },
            "permissions": {"secrets": ["secret:sec_secondary"]},
        },
        resolve,
    )

    assert migrated == {
        "auth": {
            "secret_id": "sec_primary",
            "secret_ids": ["sec_primary", "sec_secondary"],
            "secret_bindings": {"api_key": "sec_primary"},
        },
        "permissions": {"secrets": ["sec_secondary"]},
    }
    assert set(resolved) == {"secret:sec_primary", "sec_secondary", "secret:sec_secondary"}


def test_migration_stops_on_conflicting_legacy_and_current_fields():
    migration = _load_migration_module()

    with pytest.raises(RuntimeError, match="conflicting secret fields"):
        migration._migrate_payload(
            {
                "secret_ref": "secret:sec_one",
                "secret_id": "sec_two",
            },
            lambda value: value.removeprefix("secret:"),
        )


def test_migration_downgrade_restores_legacy_field_shape():
    migration = _load_migration_module()

    restored = migration._restore_payload(
        {
            "secret_id": "sec_primary",
            "secret_ids": ["sec_primary"],
            "secret_bindings": {"api_key": "sec_primary"},
        }
    )

    assert restored == {
        "secret_ref": "secret:sec_primary",
        "secret_refs": ["secret:sec_primary"],
        "secret_bindings": {"api_key": "secret:sec_primary"},
    }
