"""Phase 1.5 governance release artifact checks."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def test_phase15_governance_release_evidence_template_is_machine_verifiable() -> None:
    from scripts.verify_governance_release import (
        GovernanceReleaseEvidenceError,
        load_evidence,
        validate_governance_release_evidence,
    )

    evidence = load_evidence(
        ROOT / "docs" / "deployment" / "governance-release-v1.1.0-evidence.example.json"
    )

    report = validate_governance_release_evidence(evidence)

    assert report["passed"] is True
    assert report["release"] == "v1.1.0"
    assert report["governance_demo"] == "governance_demo_20_min"

    broken = dict(evidence)
    broken["release_tag"] = "v1.0.0"
    with pytest.raises(GovernanceReleaseEvidenceError, match="release_tag"):
        validate_governance_release_evidence(broken)

    broken_commit = dict(evidence)
    broken_commit["commit"] = "replace-with-release-commit"
    with pytest.raises(GovernanceReleaseEvidenceError, match="commit"):
        validate_governance_release_evidence(broken_commit)

    zero_commit = dict(evidence)
    zero_commit["commit"] = "0000000000000000000000000000000000000000"
    with pytest.raises(GovernanceReleaseEvidenceError, match="commit"):
        validate_governance_release_evidence(zero_commit)

    missing_tag_evidence = dict(evidence)
    missing_tag_evidence["release_commands"] = [
        command
        for command in evidence["release_commands"]
        if command.get("name") != "git_tag"
    ]
    with pytest.raises(GovernanceReleaseEvidenceError, match="git_tag"):
        validate_governance_release_evidence(missing_tag_evidence)

    duplicate_release_command = dict(evidence)
    duplicate_release_command["release_commands"] = [
        *evidence["release_commands"],
        evidence["release_commands"][0],
    ]
    with pytest.raises(GovernanceReleaseEvidenceError, match="duplicate release command"):
        validate_governance_release_evidence(duplicate_release_command)

    duplicate_demo_section = dict(evidence)
    duplicate_demo_section["governance_demo"] = {
        **evidence["governance_demo"],
        "sections": [
            *evidence["governance_demo"]["sections"],
            evidence["governance_demo"]["sections"][0],
        ],
    }
    with pytest.raises(GovernanceReleaseEvidenceError, match="duplicate governance demo section"):
        validate_governance_release_evidence(duplicate_demo_section)


def test_phase15_governance_differentiation_evidence_template_is_machine_verifiable() -> None:
    from scripts.verify_phase15_governance_differentiation import (
        GovernanceDifferentiationEvidenceError,
        load_evidence,
        validate_governance_differentiation_evidence,
    )

    evidence = load_evidence(
        ROOT
        / "docs"
        / "deployment"
        / "phase15-governance-differentiation-evidence.example.json"
    )

    report = validate_governance_differentiation_evidence(evidence)

    assert report["passed"] is True
    assert report["phase"] == "Phase 1.5"
    assert report["governance_story"] == "permissions -> secrets -> audit -> cost -> replay -> regression"

    broken = dict(evidence)
    broken["capability_sections"] = [
        section
        for section in evidence["capability_sections"]
        if section["name"] != "regression_as_release_gate"
    ]
    with pytest.raises(GovernanceDifferentiationEvidenceError, match="regression_as_release_gate"):
        validate_governance_differentiation_evidence(broken)

    duplicate_section = dict(evidence)
    duplicate_section["capability_sections"] = [
        *evidence["capability_sections"],
        evidence["capability_sections"][0],
    ]
    with pytest.raises(GovernanceDifferentiationEvidenceError, match="duplicate capability section"):
        validate_governance_differentiation_evidence(duplicate_section)

    duplicate_demo_segment = dict(evidence)
    duplicate_demo_segment["demo"] = {
        **evidence["demo"],
        "segments": [*evidence["demo"]["segments"], evidence["demo"]["segments"][0]],
    }
    with pytest.raises(GovernanceDifferentiationEvidenceError, match="duplicate demo segment"):
        validate_governance_differentiation_evidence(duplicate_demo_segment)

