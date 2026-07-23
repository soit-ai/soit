"""Validate evidence from an isolated SOIT Community restore drill."""

from __future__ import annotations

import argparse
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


class RestoreDrillEvidenceError(ValueError):
    """Raised when restore drill evidence is incomplete or inconsistent."""


def load_restore_drill_evidence(path: Path) -> dict[str, Any]:
    """Load a restore drill evidence JSON document."""

    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RestoreDrillEvidenceError("restore drill evidence must be a JSON object")
    return payload


def validate_restore_drill_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Validate RPO/RTO, component readbacks, smoke tests, and rollback evidence."""

    if evidence.get("featureKey") != "operations.restore_drill":
        raise RestoreDrillEvidenceError("featureKey must be operations.restore_drill")
    if evidence.get("schemaVersion") != 1:
        raise RestoreDrillEvidenceError("schemaVersion must be 1")

    backup_id = _require_text(evidence, "backup_id", "root")
    _require_text(evidence, "target_environment", "root")
    if evidence.get("isolated_target") is not True:
        raise RestoreDrillEvidenceError("isolated_target must be true")
    started_at = _parse_timestamp(_require_text(evidence, "startedAt", "root"), "startedAt")
    finished_at = _parse_timestamp(_require_text(evidence, "finishedAt", "root"), "finishedAt")
    if finished_at <= started_at:
        raise RestoreDrillEvidenceError("finishedAt must be after startedAt")

    manifest = _require_mapping(evidence, "backup_manifest", "root")
    _require_text(manifest, "evidence_ref", "backup_manifest")
    manifest_sha = _require_text(manifest, "sha256", "backup_manifest")
    if not SHA256_RE.fullmatch(manifest_sha):
        raise RestoreDrillEvidenceError("backup_manifest.sha256 must be lowercase SHA256")

    rpo_target = _require_positive_number(evidence, "rpo_target_minutes", "root")
    rto_target = _require_positive_number(evidence, "rto_target_minutes", "root")
    rpo = _require_non_negative_number(evidence, "rpo_minutes", "root")
    rto = _require_non_negative_number(evidence, "rto_minutes", "root")
    if rpo > rpo_target:
        raise RestoreDrillEvidenceError("rpo_minutes exceeds rpo_target_minutes")
    if rto > rto_target:
        raise RestoreDrillEvidenceError("rto_minutes exceeds rto_target_minutes")

    components = evidence.get("components")
    if not isinstance(components, dict) or set(components) != REQUIRED_COMPONENTS:
        raise RestoreDrillEvidenceError(
            f"components must be exactly {sorted(REQUIRED_COMPONENTS)}"
        )
    evidence_refs = {_require_text(manifest, "evidence_ref", "backup_manifest")}
    for name in sorted(REQUIRED_COMPONENTS):
        component = _require_mapping(components, name, "components")
        if component.get("status") != "passed":
            raise RestoreDrillEvidenceError(f"components.{name}.status must be passed")
        evidence_ref = _require_text(component, "evidence_ref", f"components.{name}")
        if evidence_ref in evidence_refs:
            raise RestoreDrillEvidenceError(f"duplicate evidence_ref: {evidence_ref}")
        evidence_refs.add(evidence_ref)

    if components["postgres"].get("row_count_readback_passed") is not True:
        raise RestoreDrillEvidenceError(
            "components.postgres.row_count_readback_passed must be true"
        )
    _require_text(components["postgres"], "alembic_revision", "components.postgres")
    if components["object_storage"].get("checksum_readback_passed") is not True:
        raise RestoreDrillEvidenceError(
            "components.object_storage.checksum_readback_passed must be true"
        )
    vector_index = components["vector_index"]
    if vector_index.get("recovery_mode") != "rebuild_from_canonical_data":
        raise RestoreDrillEvidenceError(
            "components.vector_index.recovery_mode must be rebuild_from_canonical_data"
        )
    if vector_index.get("query_readback_passed") is not True:
        raise RestoreDrillEvidenceError(
            "components.vector_index.query_readback_passed must be true"
        )
    secret_metadata = components["secret_metadata"]
    if secret_metadata.get("metadata_readback_passed") is not True:
        raise RestoreDrillEvidenceError(
            "components.secret_metadata.metadata_readback_passed must be true"
        )
    if secret_metadata.get("secret_values_rotated_or_reconnected") is not True:
        raise RestoreDrillEvidenceError(
            "components.secret_metadata.secret_values_rotated_or_reconnected must be true"
        )

    smoke_tests = evidence.get("smoke_tests")
    if not isinstance(smoke_tests, list) or not smoke_tests:
        raise RestoreDrillEvidenceError("smoke_tests must be a non-empty list")
    smoke_names: set[str] = set()
    for index, smoke in enumerate(smoke_tests):
        section = f"smoke_tests[{index}]"
        if not isinstance(smoke, dict):
            raise RestoreDrillEvidenceError(f"{section} must be an object")
        name = _require_text(smoke, "name", section)
        if name in smoke_names:
            raise RestoreDrillEvidenceError(f"duplicate smoke test: {name}")
        smoke_names.add(name)
        if smoke.get("status") != "passed":
            raise RestoreDrillEvidenceError(f"{section}.status must be passed")
        evidence_ref = _require_text(smoke, "evidence_ref", section)
        if evidence_ref in evidence_refs:
            raise RestoreDrillEvidenceError(f"duplicate evidence_ref: {evidence_ref}")
        evidence_refs.add(evidence_ref)

    rollback = _require_mapping(evidence, "rollback", "root")
    if rollback.get("tested") is not True:
        raise RestoreDrillEvidenceError("rollback.tested must be true")
    rollback_ref = _require_text(rollback, "evidence_ref", "rollback")
    if rollback_ref in evidence_refs:
        raise RestoreDrillEvidenceError(f"duplicate evidence_ref: {rollback_ref}")

    return {
        "passed": True,
        "backup_id": backup_id,
        "rpo_minutes": rpo,
        "rpo_target_minutes": rpo_target,
        "rto_minutes": rto,
        "rto_target_minutes": rto_target,
    }


def _require_mapping(parent: dict[str, Any], key: str, section: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise RestoreDrillEvidenceError(f"{section}.{key} must be an object")
    return value


def _require_text(parent: dict[str, Any], key: str, section: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RestoreDrillEvidenceError(f"{section}.{key} must be a non-empty string")
    return value.strip()


def _require_positive_number(parent: dict[str, Any], key: str, section: str) -> float:
    value = parent.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise RestoreDrillEvidenceError(f"{section}.{key} must be positive")
    return float(value)


def _require_non_negative_number(parent: dict[str, Any], key: str, section: str) -> float:
    value = parent.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        raise RestoreDrillEvidenceError(f"{section}.{key} must be non-negative")
    return float(value)


def _parse_timestamp(value: str, key: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RestoreDrillEvidenceError(f"{key} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise RestoreDrillEvidenceError(f"{key} must include a timezone")
    return parsed


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        report = validate_restore_drill_evidence(
            load_restore_drill_evidence(args.evidence)
        )
    except RestoreDrillEvidenceError as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
