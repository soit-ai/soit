"""Verify SOIT 1.0 fresh-install migration evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


class MigrationEvidenceError(ValueError):
    """Raised when migration evidence is incomplete or inconsistent."""


def load_evidence(path: Path) -> dict[str, Any]:
    """Load a migration evidence JSON document."""

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise MigrationEvidenceError("evidence document must be a JSON object")
    return data


def _require_mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise MigrationEvidenceError(f"{key} must be an object")
    return value


def _require_string(parent: dict[str, Any], key: str, *, section: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise MigrationEvidenceError(f"{section}.{key} must be a non-empty string")
    return value.strip()


def _require_bool(parent: dict[str, Any], key: str, *, section: str) -> bool:
    value = parent.get(key)
    if not isinstance(value, bool):
        raise MigrationEvidenceError(f"{section}.{key} must be a boolean")
    return value


def _require_passed_records(
    parent: dict[str, Any], key: str, *, section: str
) -> list[dict[str, Any]]:
    records = parent.get(key)
    if not isinstance(records, list) or not records:
        raise MigrationEvidenceError(f"{section}.{key} must be a non-empty list")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise MigrationEvidenceError(f"{section}.{key}[{index}] must be an object")
        if record.get("exit_code") != 0 and record.get("passed") is not True:
            raise MigrationEvidenceError(f"{section}.{key}[{index}] did not pass")
        _require_string(record, "command", section=f"{section}.{key}[{index}]")
    return records


def _validate_alembic_heads(evidence: dict[str, Any], head_revision: str) -> None:
    heads = _require_mapping(evidence, "alembic_heads")
    _require_passed_records({"commands": [heads]}, "commands", section="alembic_heads")
    reported_revision = _require_string(heads, "revision", section="alembic_heads")
    if reported_revision != head_revision:
        raise MigrationEvidenceError(
            f"alembic_heads.revision {reported_revision!r} does not match "
            f"head_revision {head_revision!r}"
        )
    if _require_bool(heads, "single_head", section="alembic_heads") is not True:
        raise MigrationEvidenceError("alembic_heads.single_head must be true")


def _validate_fresh_install(section: dict[str, Any], head_revision: str) -> str:
    _require_string(section, "database_kind", section="fresh_install")
    if _require_bool(section, "started_empty", section="fresh_install") is not True:
        raise MigrationEvidenceError("fresh_install.started_empty must be true")
    post_revision = _require_string(
        section, "post_upgrade_revision", section="fresh_install"
    )
    if post_revision != head_revision:
        raise MigrationEvidenceError(
            f"fresh_install.post_upgrade_revision {post_revision!r} does not match "
            f"head_revision {head_revision!r}"
        )
    _require_passed_records(section, "commands", section="fresh_install")
    _require_passed_records(section, "schema_checks", section="fresh_install")
    _require_passed_records(section, "smoke_tests", section="fresh_install")
    _require_passed_records(section, "demo_seed_commands", section="fresh_install")
    return post_revision


def validate_migration_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Validate the supported fresh-install-only migration evidence."""

    if evidence.get("featureKey") != "release.fresh_install_migration":
        raise MigrationEvidenceError(
            "featureKey must be release.fresh_install_migration"
        )
    if "development_database" in evidence:
        raise MigrationEvidenceError(
            "development database upgrades are no longer supported"
        )

    started_at = _parse_timestamp(_require_string(evidence, "startedAt", section="root"))
    finished_at = _parse_timestamp(_require_string(evidence, "finishedAt", section="root"))
    if finished_at <= started_at:
        raise MigrationEvidenceError("finishedAt must be after startedAt")

    head_revision = _require_string(evidence, "head_revision", section="root")
    _validate_alembic_heads(evidence, head_revision)
    fresh_revision = _validate_fresh_install(
        _require_mapping(evidence, "fresh_install"), head_revision
    )

    release_notes = _require_mapping(evidence, "release_notes")
    _require_string(release_notes, "path", section="release_notes")
    migration_range = _require_string(
        release_notes, "migration_range", section="release_notes"
    )
    expected_range = f"base..{head_revision}"
    if migration_range != expected_range:
        raise MigrationEvidenceError(
            f"release_notes.migration_range must be {expected_range}"
        )

    return {
        "passed": True,
        "head_revision": head_revision,
        "paths": {"fresh_install": fresh_revision},
    }


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise MigrationEvidenceError(f"invalid ISO timestamp: {value}") from exc


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify SOIT 1.0 fresh-install migration evidence."
    )
    parser.add_argument("evidence", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        report = validate_migration_evidence(load_evidence(args.evidence))
    except MigrationEvidenceError as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
