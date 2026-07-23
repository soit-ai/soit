"""Validate a SOIT Community backup manifest and its optional local files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_COMPONENTS = {
    "postgres",
    "object_storage",
    "vector_index",
    "secret_metadata",
}


class BackupManifestError(ValueError):
    """Raised when a backup manifest is incomplete or inconsistent."""


def load_backup_manifest(path: Path) -> dict[str, Any]:
    """Load a backup manifest JSON document."""

    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise BackupManifestError("backup manifest must be a JSON object")
    return payload


def validate_backup_manifest(
    manifest: dict[str, Any],
    *,
    backup_root: Path | None = None,
) -> dict[str, Any]:
    """Validate manifest structure, recovery semantics, and optional file hashes."""

    if manifest.get("featureKey") != "operations.backup_manifest":
        raise BackupManifestError("featureKey must be operations.backup_manifest")
    if manifest.get("schemaVersion") != 1:
        raise BackupManifestError("schemaVersion must be 1")

    backup_id = _require_text(manifest, "backup_id", "root")
    _require_text(manifest, "platform_version", "root")
    alembic_revision = _require_text(manifest, "alembic_revision", "root")
    started_at = _parse_timestamp(_require_text(manifest, "startedAt", "root"), "startedAt")
    finished_at = _parse_timestamp(_require_text(manifest, "finishedAt", "root"), "finishedAt")
    if finished_at <= started_at:
        raise BackupManifestError("finishedAt must be after startedAt")
    _require_positive_number(manifest, "rpo_target_minutes", "root")
    _require_positive_number(manifest, "rto_target_minutes", "root")

    raw_files = manifest.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise BackupManifestError("files must be a non-empty list")
    files: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(raw_files):
        section = f"files[{index}]"
        if not isinstance(record, dict):
            raise BackupManifestError(f"{section} must be an object")
        relative_path = _require_text(record, "path", section)
        normalized_path = Path(relative_path)
        if normalized_path.is_absolute() or ".." in normalized_path.parts:
            raise BackupManifestError(f"{section}.path must stay within the backup root")
        if relative_path in files:
            raise BackupManifestError(f"duplicate backup file path: {relative_path}")
        digest = _require_text(record, "sha256", section)
        if not SHA256_RE.fullmatch(digest):
            raise BackupManifestError(f"{section}.sha256 must be lowercase SHA256")
        size_bytes = record.get("size_bytes")
        if not isinstance(size_bytes, int) or size_bytes < 0:
            raise BackupManifestError(f"{section}.size_bytes must be a non-negative integer")
        files[relative_path] = record

    components = manifest.get("components")
    if not isinstance(components, dict):
        raise BackupManifestError("components must be an object")
    if set(components) != REQUIRED_COMPONENTS:
        raise BackupManifestError(
            f"components must be exactly {sorted(REQUIRED_COMPONENTS)}"
        )

    postgres = _require_mapping(components, "postgres", "components")
    if postgres.get("strategy") != "pg_dump_custom":
        raise BackupManifestError("components.postgres.strategy must be pg_dump_custom")
    _validate_component_files(postgres, "components.postgres", files, require_nonempty=True)

    object_storage = _require_mapping(components, "object_storage", "components")
    if object_storage.get("strategy") != "object_mirror":
        raise BackupManifestError(
            "components.object_storage.strategy must be object_mirror"
        )
    _validate_component_files(
        object_storage,
        "components.object_storage",
        files,
        require_nonempty=False,
    )

    vector_index = _require_mapping(components, "vector_index", "components")
    if vector_index.get("recovery_mode") != "rebuild_from_canonical_data":
        raise BackupManifestError(
            "components.vector_index.recovery_mode must be rebuild_from_canonical_data"
        )
    if vector_index.get("canonical_sources") != ["postgres", "object_storage"]:
        raise BackupManifestError(
            "components.vector_index.canonical_sources must be postgres and object_storage"
        )
    if vector_index.get("files") != []:
        raise BackupManifestError("components.vector_index.files must be empty")

    secret_metadata = _require_mapping(components, "secret_metadata", "components")
    if secret_metadata.get("recovery_mode") != "postgres_metadata":
        raise BackupManifestError(
            "components.secret_metadata.recovery_mode must be postgres_metadata"
        )
    if secret_metadata.get("secret_values_included") is not False:
        raise BackupManifestError("backup manifests must not claim to include secret values")
    _validate_component_files(
        secret_metadata,
        "components.secret_metadata",
        files,
        require_nonempty=True,
    )

    if backup_root is not None:
        root = backup_root.resolve()
        for relative_path, record in files.items():
            path = (root / relative_path).resolve()
            if root not in path.parents:
                raise BackupManifestError(f"backup file escapes root: {relative_path}")
            if not path.is_file():
                raise BackupManifestError(f"backup file does not exist: {relative_path}")
            content = path.read_bytes()
            if len(content) != record["size_bytes"]:
                raise BackupManifestError(f"backup file size mismatch: {relative_path}")
            if hashlib.sha256(content).hexdigest() != record["sha256"]:
                raise BackupManifestError(f"backup file checksum mismatch: {relative_path}")

    return {
        "passed": True,
        "backup_id": backup_id,
        "alembic_revision": alembic_revision,
        "file_count": len(files),
    }


def _validate_component_files(
    component: dict[str, Any],
    section: str,
    files: dict[str, dict[str, Any]],
    *,
    require_nonempty: bool,
) -> None:
    values = component.get("files")
    if not isinstance(values, list) or (require_nonempty and not values):
        qualifier = "non-empty " if require_nonempty else ""
        raise BackupManifestError(f"{section}.files must be a {qualifier}list")
    if len(values) != len(set(values)):
        raise BackupManifestError(f"{section}.files must be unique")
    for value in values:
        if value not in files:
            raise BackupManifestError(f"{section}.files references an unknown file: {value}")


def _require_mapping(parent: dict[str, Any], key: str, section: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise BackupManifestError(f"{section}.{key} must be an object")
    return value


def _require_text(parent: dict[str, Any], key: str, section: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BackupManifestError(f"{section}.{key} must be a non-empty string")
    return value.strip()


def _require_positive_number(parent: dict[str, Any], key: str, section: str) -> float:
    value = parent.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise BackupManifestError(f"{section}.{key} must be positive")
    return float(value)


def _parse_timestamp(value: str, key: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BackupManifestError(f"{key} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise BackupManifestError(f"{key} must include a timezone")
    return parsed


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--backup-root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        report = validate_backup_manifest(
            load_backup_manifest(args.manifest),
            backup_root=args.backup_root,
        )
    except BackupManifestError as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
