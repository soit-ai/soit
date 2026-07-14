"""Verify SOIT Community Phase 1.5 exit gap report."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

FEATURE_KEY = "phase15.exit_gap_report"
REQUIRED_LOCAL_COVERAGE = {
    "phase15.governance_differentiation",
    "phase15.governance_release_template",
    "phase15.release_notes_draft",
}
REQUIRED_MISSING_EXTERNAL_EVIDENCE = {
    "release.v1_1_tag_and_notes",
    "release.clean_governance_release_commit",
    "release.remote_quality_gates",
}
ALLOWED_LOCAL_STATUSES = {"local_verified", "local_template", "local_draft"}


class Phase15ExitGapReportError(ValueError):
    """Raised when Phase 1.5 exit gap report evidence is incomplete or unsafe."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Path to Phase 1.5 exit gap report JSON")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="SOIT Community repository root used to resolve local evidence refs",
    )
    args = parser.parse_args()

    report = _load_json(args.report)
    result = validate_phase15_exit_gap_report(report, repo_root=args.repo_root)
    print(f"phase15 exit gap report verified: {result['feature_key']}")
    return 0


def validate_phase15_exit_gap_report(report: dict[str, Any], *, repo_root: Path) -> dict[str, Any]:
    if report.get("featureKey") != FEATURE_KEY:
        raise Phase15ExitGapReportError(f"featureKey must be {FEATURE_KEY}")
    if report.get("status") != "not_complete":
        raise Phase15ExitGapReportError("status must be not_complete")
    _parse_timestamp(_require_text(report, "generatedAt"), "generatedAt")

    release_ref = _require_text(report, "governanceReleaseEvidenceRef")
    _require_existing_ref(release_ref, repo_root=repo_root)

    local_count = _verify_local_coverage(report, repo_root=repo_root)
    missing_count = _verify_missing_external_evidence(report)
    _verify_roadmap_decision(report)

    return {
        "feature_key": FEATURE_KEY,
        "local_evidence_count": local_count,
        "missing_external_evidence_count": missing_count,
    }


def _verify_local_coverage(report: dict[str, Any], *, repo_root: Path) -> int:
    coverage = report.get("localEvidenceCoverage")
    if not isinstance(coverage, list):
        raise Phase15ExitGapReportError("localEvidenceCoverage must be a list")

    keys: set[str] = set()
    evidence_refs: set[str] = set()
    for item in coverage:
        if not isinstance(item, dict):
            raise Phase15ExitGapReportError("localEvidenceCoverage entries must be objects")
        requirement_key = _require_text(item, "requirementKey")
        if requirement_key in keys:
            raise Phase15ExitGapReportError(f"duplicate localEvidenceCoverage requirementKey: {requirement_key}")
        keys.add(requirement_key)

        status = _require_text(item, "status")
        if status not in ALLOWED_LOCAL_STATUSES:
            raise Phase15ExitGapReportError(
                f"localEvidenceCoverage.{requirement_key}.status must be one of {sorted(ALLOWED_LOCAL_STATUSES)}"
            )

        evidence_ref = _require_text(item, "evidenceRef")
        if evidence_ref in evidence_refs:
            raise Phase15ExitGapReportError(f"duplicate localEvidenceCoverage evidenceRef: {evidence_ref}")
        evidence_refs.add(evidence_ref)
        _require_existing_ref(evidence_ref, repo_root=repo_root)

    missing = REQUIRED_LOCAL_COVERAGE - keys
    if missing:
        raise Phase15ExitGapReportError(f"localEvidenceCoverage missing requirements: {sorted(missing)}")
    return len(coverage)


def _verify_missing_external_evidence(report: dict[str, Any]) -> int:
    missing_evidence = report.get("missingExternalEvidence")
    if not isinstance(missing_evidence, list):
        raise Phase15ExitGapReportError("missingExternalEvidence must be a list")

    keys: set[str] = set()
    for item in missing_evidence:
        if not isinstance(item, dict):
            raise Phase15ExitGapReportError("missingExternalEvidence entries must be objects")
        requirement_key = _require_text(item, "requirementKey")
        if requirement_key in keys:
            raise Phase15ExitGapReportError(f"duplicate missingExternalEvidence requirementKey: {requirement_key}")
        keys.add(requirement_key)
        _require_text(item, "missingEvidence")
        roadmap_ref = _require_text(item, "roadmapRef")
        if "SOIT_Long_Term_Roadmap_v1.md" not in roadmap_ref:
            raise Phase15ExitGapReportError(
                f"missingExternalEvidence.{requirement_key}.roadmapRef must reference SOIT_Long_Term_Roadmap_v1.md"
            )

    missing = REQUIRED_MISSING_EXTERNAL_EVIDENCE - keys
    if missing:
        raise Phase15ExitGapReportError(f"missingExternalEvidence missing requirements: {sorted(missing)}")
    return len(missing_evidence)


def _verify_roadmap_decision(report: dict[str, Any]) -> None:
    decision = report.get("roadmapDecision")
    if not isinstance(decision, dict):
        raise Phase15ExitGapReportError("roadmapDecision must be an object")
    if decision.get("mayCheckPhase15Exit") is not False:
        raise Phase15ExitGapReportError("roadmapDecision.mayCheckPhase15Exit must be false")
    _require_text(decision, "reason")


def _require_existing_ref(evidence_ref: str, *, repo_root: Path) -> None:
    if _is_external_ref(evidence_ref):
        raise Phase15ExitGapReportError(f"local evidenceRef must be repository-relative: {evidence_ref}")
    path = (repo_root / evidence_ref).resolve()
    repo = repo_root.resolve()
    if repo not in (path, *path.parents):
        raise Phase15ExitGapReportError(f"evidenceRef escapes repository root: {evidence_ref}")
    if not path.is_file():
        raise Phase15ExitGapReportError(f"evidenceRef does not exist: {evidence_ref}")


def _is_external_ref(value: str) -> bool:
    return "://" in value or value.startswith("local-http:")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise Phase15ExitGapReportError("report must be a JSON object")
    return payload


def _require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise Phase15ExitGapReportError(f"{key} must be a non-empty string")
    return value.strip()


def _parse_timestamp(value: str, key: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Phase15ExitGapReportError(f"{key} must be an ISO-8601 timestamp") from exc


if __name__ == "__main__":
    raise SystemExit(main())
