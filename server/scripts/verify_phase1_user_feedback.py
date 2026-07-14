"""Verify SOIT 1.0 non-developer user feedback evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

REQUIRED_COMPLETED_CHAIN = "chain_a"
REQUIRED_DECISIONS = {"go", "go_with_known_limitations", "no_go"}


class UserFeedbackEvidenceError(ValueError):
    """Raised when non-developer user feedback evidence is incomplete or invalid."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="Path to Phase 1 user feedback evidence JSON")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root used to require local evidenceRef files",
    )
    args = parser.parse_args()

    evidence = load_evidence(args.evidence)
    report = validate_user_feedback_evidence(evidence, repo_root=args.repo_root)
    print(f"phase1 user feedback evidence verified: {report['feedback_id']}")
    return 0


def load_evidence(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise UserFeedbackEvidenceError("evidence must be a JSON object")
    return payload


def validate_user_feedback_evidence(
    evidence: dict[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    if evidence.get("featureKey") != "phase1.non_developer_feedback":
        raise UserFeedbackEvidenceError("featureKey must be phase1.non_developer_feedback")
    for key in ("feedbackId", "release", "environment", "operator", "startedAt", "finishedAt"):
        _require_text(evidence, key)
    started_at = _parse_timestamp(_require_text(evidence, "startedAt"), "startedAt")
    finished_at = _parse_timestamp(_require_text(evidence, "finishedAt"), "finishedAt")
    if finished_at <= started_at:
        raise UserFeedbackEvidenceError("finishedAt must be after startedAt")

    participants = evidence.get("participants")
    if not isinstance(participants, list):
        raise UserFeedbackEvidenceError("participants must be a list")
    if not 1 <= len(participants) <= 3:
        raise UserFeedbackEvidenceError("participants must include 1 to 3 non-developer users")
    participant_refs: set[str] = set()
    for index, participant in enumerate(participants):
        if not isinstance(participant, dict):
            raise UserFeedbackEvidenceError(f"participants[{index}] must be an object")
        _validate_participant(participant, f"participants[{index}]", started_at, finished_at)
        user_ref = str(participant["userRef"]).strip()
        if user_ref in participant_refs:
            raise UserFeedbackEvidenceError("participants.userRef values must be unique")
        participant_refs.add(user_ref)

    decision = evidence.get("releaseDecision")
    if not isinstance(decision, dict):
        raise UserFeedbackEvidenceError("releaseDecision must be an object")
    if decision.get("decision") not in REQUIRED_DECISIONS:
        raise UserFeedbackEvidenceError(
            f"releaseDecision.decision must be one of {sorted(REQUIRED_DECISIONS)}",
        )
    for key in ("reviewer", "decisionRef", "knownLimitationsRef"):
        _require_text(decision, key)

    if repo_root is not None:
        for participant in participants:
            _require_existing_ref(_require_text(participant, "feedbackRef"), repo_root=repo_root)
        for key in ("decisionRef", "knownLimitationsRef"):
            _require_existing_ref(_require_text(decision, key), repo_root=repo_root)

    return {
        "passed": True,
        "feedback_id": evidence["feedbackId"],
        "participant_count": len(participants),
        "completed_chain": REQUIRED_COMPLETED_CHAIN,
    }


def _validate_participant(
    participant: dict[str, Any],
    path: str,
    started_at: datetime,
    finished_at: datetime,
) -> None:
    for key in ("userRef", "role", "completedChain", "completedAt", "feedbackRef"):
        _require_text(participant, key)
    completed_at = _parse_timestamp(_require_text(participant, "completedAt"), f"{path}.completedAt")
    if completed_at < started_at or completed_at > finished_at:
        raise UserFeedbackEvidenceError(f"{path}.completedAt must be inside the feedback window")
    role = str(participant["role"]).strip().lower()
    if "developer" in role or "engineer" in role:
        raise UserFeedbackEvidenceError(f"{path}.role must describe a non-developer user")
    if participant.get("completedChain") != REQUIRED_COMPLETED_CHAIN:
        raise UserFeedbackEvidenceError(f"{path}.completedChain must be {REQUIRED_COMPLETED_CHAIN}")
    if participant.get("status") != "passed":
        raise UserFeedbackEvidenceError(f"{path}.status must be passed")
    rating = participant.get("rating")
    if not isinstance(rating, int) or not 1 <= rating <= 5:
        raise UserFeedbackEvidenceError(f"{path}.rating must be an integer from 1 to 5")
    blockers = participant.get("blockingIssues")
    if not isinstance(blockers, list):
        raise UserFeedbackEvidenceError(f"{path}.blockingIssues must be a list")
    if blockers:
        raise UserFeedbackEvidenceError(f"{path}.blockingIssues must be empty for release acceptance")


def _require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise UserFeedbackEvidenceError(f"{key} must be a non-empty string")
    return value.strip()


def _parse_timestamp(value: str, key: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise UserFeedbackEvidenceError(f"{key} must be an ISO-8601 timestamp") from exc


def _require_existing_ref(evidence_ref: str, *, repo_root: Path) -> None:
    if "://" in evidence_ref or evidence_ref.startswith("local-http:"):
        raise UserFeedbackEvidenceError(f"evidenceRef must be repository-relative: {evidence_ref}")
    ref_path = evidence_ref.split("#", 1)[0]
    path = (repo_root / ref_path).resolve()
    repo = repo_root.resolve()
    if repo not in (path, *path.parents):
        raise UserFeedbackEvidenceError(f"evidenceRef escapes repository root: {evidence_ref}")
    if not path.is_file():
        raise UserFeedbackEvidenceError(f"evidenceRef does not exist: {evidence_ref}")


if __name__ == "__main__":
    raise SystemExit(main())
