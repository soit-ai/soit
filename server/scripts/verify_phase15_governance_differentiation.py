"""Verify Phase 1.5 governance differentiation evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_PHASE = "Phase 1.5"
EXPECTED_STORY = "permissions -> secrets -> audit -> cost -> replay -> regression"
REQUIRED_SECTIONS = {
    "plugin_first_governance",
    "observe_governance_surfaces",
    "regression_as_release_gate",
    "architecture_gap_review",
    "customer_governance_demo",
}
REQUIRED_DEMO_SEGMENTS = {
    "permissions",
    "secrets",
    "call_audit",
    "cost_attribution",
    "replay",
    "regression",
}


class GovernanceDifferentiationEvidenceError(ValueError):
    """Raised when Phase 1.5 governance differentiation evidence is incomplete."""


def load_evidence(path: Path) -> dict[str, Any]:
    """Load a Phase 1.5 governance differentiation evidence JSON document."""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise GovernanceDifferentiationEvidenceError("evidence document must be a JSON object")
    return data


def _require_string(parent: dict[str, Any], key: str, *, section: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GovernanceDifferentiationEvidenceError(f"{section}.{key} must be a non-empty string")
    return value.strip()


def _require_bool(parent: dict[str, Any], key: str, *, section: str) -> bool:
    value = parent.get(key)
    if not isinstance(value, bool):
        raise GovernanceDifferentiationEvidenceError(f"{section}.{key} must be a boolean")
    return value


def _require_strings(parent: dict[str, Any], key: str, *, section: str) -> list[str]:
    values = parent.get(key)
    if not isinstance(values, list) or not values:
        raise GovernanceDifferentiationEvidenceError(f"{section}.{key} must be a non-empty list")
    normalized: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise GovernanceDifferentiationEvidenceError(
                f"{section}.{key}[{index}] must be a non-empty string"
            )
        normalized.append(value.strip())
    return normalized


def _require_passed_records(parent: dict[str, Any], key: str, *, section: str) -> None:
    records = parent.get(key)
    if not isinstance(records, list) or not records:
        raise GovernanceDifferentiationEvidenceError(f"{section}.{key} must be a non-empty list")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise GovernanceDifferentiationEvidenceError(f"{section}.{key}[{index}] must be an object")
        _require_string(record, "command", section=f"{section}.{key}[{index}]")
        if record.get("exit_code") != 0 and record.get("passed") is not True:
            raise GovernanceDifferentiationEvidenceError(f"{section}.{key}[{index}] did not pass")


def _validate_capability_sections(evidence: dict[str, Any]) -> set[str]:
    sections = evidence.get("capability_sections")
    if not isinstance(sections, list) or not sections:
        raise GovernanceDifferentiationEvidenceError("capability_sections must be a non-empty list")

    names: set[str] = set()
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            raise GovernanceDifferentiationEvidenceError(f"capability_sections[{index}] must be an object")
        section_name = _require_string(section, "name", section=f"capability_sections[{index}]")
        if section_name in names:
            raise GovernanceDifferentiationEvidenceError(f"duplicate capability section: {section_name}")
        names.add(section_name)
        if _require_bool(section, "complete", section=section_name) is not True:
            raise GovernanceDifferentiationEvidenceError(f"{section_name}.complete must be true")
        _require_strings(section, "evidence_refs", section=section_name)
        _require_passed_records(section, "verification", section=section_name)

    missing = REQUIRED_SECTIONS - names
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise GovernanceDifferentiationEvidenceError(
            f"capability_sections missing required sections: {missing_list}"
        )
    return names


def _validate_demo(evidence: dict[str, Any]) -> None:
    demo = evidence.get("demo")
    if not isinstance(demo, dict):
        raise GovernanceDifferentiationEvidenceError("demo must be an object")
    if _require_bool(demo, "complete", section="demo") is not True:
        raise GovernanceDifferentiationEvidenceError("demo.complete must be true")
    segment_entries = _require_strings(demo, "segments", section="demo")
    if len(set(segment_entries)) != len(segment_entries):
        raise GovernanceDifferentiationEvidenceError("duplicate demo segment")
    segments = set(segment_entries)
    if segments != REQUIRED_DEMO_SEGMENTS:
        raise GovernanceDifferentiationEvidenceError(
            "demo.segments must cover permissions, secrets, call_audit, cost_attribution, replay, and regression"
        )
    _require_passed_records(demo, "verification", section="demo")


def validate_governance_differentiation_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Validate Phase 1.5 governance differentiation evidence."""
    phase = _require_string(evidence, "phase", section="root")
    if phase != EXPECTED_PHASE:
        raise GovernanceDifferentiationEvidenceError(
            f"phase {phase!r} does not match {EXPECTED_PHASE!r}"
        )
    governance_story = _require_string(evidence, "governance_story", section="root")
    if governance_story != EXPECTED_STORY:
        raise GovernanceDifferentiationEvidenceError(
            f"governance_story {governance_story!r} does not match {EXPECTED_STORY!r}"
        )
    _validate_capability_sections(evidence)
    _validate_demo(evidence)
    _require_passed_records(evidence, "release_readiness_gates", section="root")

    return {
        "passed": True,
        "phase": phase,
        "governance_story": governance_story,
        "capability_sections": sorted(REQUIRED_SECTIONS),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Phase 1.5 governance differentiation evidence."
    )
    parser.add_argument("evidence", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        report = validate_governance_differentiation_evidence(load_evidence(args.evidence))
    except GovernanceDifferentiationEvidenceError as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
