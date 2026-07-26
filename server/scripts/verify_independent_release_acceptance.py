"""Verify independent clean-environment release acceptance evidence."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

REQUIRED_JOURNEYS = {
    "fresh_install",
    "empty_workspace_knowledge_agent_observe",
    "empty_workspace_workflow",
}
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class IndependentReleaseAcceptanceError(ValueError):
    """Raised when independent release acceptance evidence is incomplete."""


def load_evidence(path: Path) -> dict[str, Any]:
    """Load an independent release acceptance evidence document."""
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise IndependentReleaseAcceptanceError("evidence must be a JSON object")
    return payload


def validate_independent_release_acceptance(
    evidence: dict[str, Any],
    *,
    evidence_root: Path | None = None,
) -> dict[str, Any]:
    """Fail closed unless two or three independent clean runs passed."""
    if evidence.get("featureKey") != "release.independent_acceptance":
        raise IndependentReleaseAcceptanceError(
            "featureKey must be release.independent_acceptance"
        )
    acceptance_id = _require_text(evidence, "acceptanceId", "root")
    _require_text(evidence, "release", "root")
    commit = _require_text(evidence, "commit", "root")
    if not COMMIT_PATTERN.fullmatch(commit):
        raise IndependentReleaseAcceptanceError(
            "root.commit must be a lowercase 40-character Git commit"
        )
    _require_text(evidence, "acceptanceScriptRef", "root")
    started_at = _parse_timestamp(_require_text(evidence, "startedAt", "root"), "root.startedAt")
    finished_at = _parse_timestamp(
        _require_text(evidence, "finishedAt", "root"), "root.finishedAt"
    )
    if finished_at <= started_at:
        raise IndependentReleaseAcceptanceError("root.finishedAt must be after root.startedAt")

    reviewers = evidence.get("reviewers")
    if not isinstance(reviewers, list) or not 2 <= len(reviewers) <= 3:
        raise IndependentReleaseAcceptanceError("reviewers must include 2 to 3 people")

    reviewer_refs: set[str] = set()
    environment_refs: set[str] = set()
    evidence_refs: list[str] = []
    latest_review_finish = started_at
    for index, reviewer in enumerate(reviewers):
        if not isinstance(reviewer, dict):
            raise IndependentReleaseAcceptanceError(f"reviewers[{index}] must be an object")
        section = f"reviewers[{index}]"
        reviewer_ref = _require_text(reviewer, "reviewerRef", section)
        if reviewer_ref in reviewer_refs:
            raise IndependentReleaseAcceptanceError("reviewers.reviewerRef values must be unique")
        reviewer_refs.add(reviewer_ref)
        role = _require_text(reviewer, "role", section).lower()
        if "developer" in role or "engineer" in role:
            raise IndependentReleaseAcceptanceError(
                f"{section}.role must describe a non-code author"
            )
        if reviewer.get("codeAuthor") is not False:
            raise IndependentReleaseAcceptanceError(f"{section}.codeAuthor must be false")
        if reviewer.get("cleanEnvironment") is not True:
            raise IndependentReleaseAcceptanceError(
                f"{section}.cleanEnvironment must be true"
            )
        if reviewer.get("sourceCommit") != commit:
            raise IndependentReleaseAcceptanceError(
                f"{section}.sourceCommit must match root.commit"
            )

        environment_ref = _require_text(reviewer, "environmentRef", section)
        if environment_ref in environment_refs:
            raise IndependentReleaseAcceptanceError(
                "reviewers.environmentRef values must identify independent environments"
            )
        environment_refs.add(environment_ref)

        review_started = _parse_timestamp(
            _require_text(reviewer, "startedAt", section), f"{section}.startedAt"
        )
        review_finished = _parse_timestamp(
            _require_text(reviewer, "finishedAt", section), f"{section}.finishedAt"
        )
        if not started_at <= review_started < review_finished <= finished_at:
            raise IndependentReleaseAcceptanceError(
                f"{section} timestamps must be inside the root acceptance window"
            )
        latest_review_finish = max(latest_review_finish, review_finished)

        duration = reviewer.get("durationMinutes")
        if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
            raise IndependentReleaseAcceptanceError(
                f"{section}.durationMinutes must be a positive integer"
            )
        if reviewer.get("completionRatePercent") != 100:
            raise IndependentReleaseAcceptanceError(
                f"{section}.completionRatePercent must be 100"
            )
        journeys = reviewer.get("completedJourneys")
        if not isinstance(journeys, list) or not all(
            isinstance(item, str) and item.strip() for item in journeys
        ):
            raise IndependentReleaseAcceptanceError(
                f"{section}.completedJourneys must be a list of names"
            )
        missing_journeys = REQUIRED_JOURNEYS - set(journeys)
        if missing_journeys:
            raise IndependentReleaseAcceptanceError(
                f"{section}.completedJourneys missing {sorted(missing_journeys)}"
            )
        blockers = reviewer.get("blockingIssues")
        if not isinstance(blockers, list) or blockers:
            raise IndependentReleaseAcceptanceError(
                f"{section}.blockingIssues must be an empty list"
            )
        if reviewer.get("result") != "passed":
            raise IndependentReleaseAcceptanceError(f"{section}.result must be passed")

        for key in ("environmentRef", "evidenceRef", "signatureRef"):
            evidence_refs.append(_require_text(reviewer, key, section))
        signed_at = _parse_timestamp(
            _require_text(reviewer, "signedAt", section), f"{section}.signedAt"
        )
        if not review_finished <= signed_at <= finished_at:
            raise IndependentReleaseAcceptanceError(
                f"{section}.signedAt must be after the run and inside the acceptance window"
            )

    decision = evidence.get("releaseDecision")
    if not isinstance(decision, dict):
        raise IndependentReleaseAcceptanceError("releaseDecision must be an object")
    if decision.get("result") != "passed":
        raise IndependentReleaseAcceptanceError("releaseDecision.result must be passed")
    _require_text(decision, "signer", "releaseDecision")
    decision_signature = _require_text(decision, "signatureRef", "releaseDecision")
    evidence_refs.append(decision_signature)
    decision_signed_at = _parse_timestamp(
        _require_text(decision, "signedAt", "releaseDecision"),
        "releaseDecision.signedAt",
    )
    if not latest_review_finish <= decision_signed_at <= finished_at:
        raise IndependentReleaseAcceptanceError(
            "releaseDecision.signedAt must follow all reviewer runs"
        )

    if evidence_root is not None:
        for evidence_ref in evidence_refs:
            _require_existing_ref(evidence_ref, evidence_root=evidence_root)

    return {
        "passed": True,
        "acceptance_id": acceptance_id,
        "commit": commit,
        "reviewer_count": len(reviewers),
    }


def _require_text(payload: dict[str, Any], key: str, section: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise IndependentReleaseAcceptanceError(
            f"{section}.{key} must be a non-empty string"
        )
    return value.strip()


def _parse_timestamp(value: str, key: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IndependentReleaseAcceptanceError(
            f"{key} must be an ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise IndependentReleaseAcceptanceError(f"{key} must include a timezone")
    return parsed


def _require_existing_ref(evidence_ref: str, *, evidence_root: Path) -> None:
    if "://" in evidence_ref or Path(evidence_ref).is_absolute():
        raise IndependentReleaseAcceptanceError(
            f"evidence reference must be relative: {evidence_ref}"
        )
    path = (evidence_root / evidence_ref.split("#", 1)[0]).resolve()
    root = evidence_root.resolve()
    if root not in (path, *path.parents):
        raise IndependentReleaseAcceptanceError(
            f"evidence reference escapes evidence root: {evidence_ref}"
        )
    if not path.is_file():
        raise IndependentReleaseAcceptanceError(
            f"evidence reference does not exist: {evidence_ref}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="Acceptance evidence JSON")
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=None,
        help="Root used to require reviewer environment, run, and signature files",
    )
    args = parser.parse_args()
    report = validate_independent_release_acceptance(
        load_evidence(args.evidence),
        evidence_root=args.evidence_root,
    )
    print(
        "independent release acceptance verified: "
        f"{report['acceptance_id']} ({report['reviewer_count']} reviewers)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
