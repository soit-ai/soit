"""Independent release acceptance evidence contract tests."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from scripts.verify_independent_release_acceptance import (
    IndependentReleaseAcceptanceError,
    load_evidence,
    validate_independent_release_acceptance,
)

ROOT = Path(__file__).resolve().parents[3]


def test_independent_release_acceptance_requires_two_clean_nonauthor_runs() -> None:
    evidence = load_evidence(
        ROOT
        / "docs"
        / "deployment"
        / "independent-release-acceptance.example.json"
    )

    report = validate_independent_release_acceptance(evidence)

    assert report == {
        "passed": True,
        "acceptance_id": "rc1-independent-acceptance-20260723",
        "commit": "0123456789abcdef0123456789abcdef01234567",
        "reviewer_count": 2,
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: payload["reviewers"].pop(), "2 to 3"),
        (
            lambda payload: payload["reviewers"][0].update({"codeAuthor": True}),
            "codeAuthor",
        ),
        (
            lambda payload: payload["reviewers"][0].update(
                {"role": "software engineer", "codeAuthor": False}
            ),
            "role",
        ),
        (
            lambda payload: payload["reviewers"][0].update({"cleanEnvironment": False}),
            "cleanEnvironment",
        ),
        (
            lambda payload: payload["reviewers"][0].update({"completionRatePercent": 99}),
            "completionRatePercent",
        ),
        (
            lambda payload: payload["reviewers"][0]["blockingIssues"].append("startup failed"),
            "blockingIssues",
        ),
        (
            lambda payload: payload["reviewers"][0].update(
                {"completedJourneys": ["fresh_install"]}
            ),
            "completedJourneys",
        ),
    ],
)
def test_independent_release_acceptance_fails_closed(
    mutation: Callable[[dict[str, Any]], object],
    message: str,
) -> None:
    evidence = load_evidence(
        ROOT
        / "docs"
        / "deployment"
        / "independent-release-acceptance.example.json"
    )
    broken = deepcopy(evidence)
    mutation(broken)

    with pytest.raises(IndependentReleaseAcceptanceError, match=message):
        validate_independent_release_acceptance(broken)


def test_independent_release_acceptance_strict_mode_requires_signed_evidence(
    tmp_path: Path,
) -> None:
    evidence = load_evidence(
        ROOT
        / "docs"
        / "deployment"
        / "independent-release-acceptance.example.json"
    )
    evidence_root = tmp_path / "acceptance"
    evidence_root.mkdir()
    refs = [
        reviewer[key]
        for reviewer in evidence["reviewers"]
        for key in ("environmentRef", "evidenceRef", "signatureRef")
    ]
    refs.append(evidence["releaseDecision"]["signatureRef"])
    for ref in refs:
        path = evidence_root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{ref}\n", encoding="utf-8")

    report = validate_independent_release_acceptance(
        evidence,
        evidence_root=evidence_root,
    )

    assert report["passed"] is True
    (evidence_root / refs[0]).unlink()
    with pytest.raises(IndependentReleaseAcceptanceError, match="does not exist"):
        validate_independent_release_acceptance(evidence, evidence_root=evidence_root)
