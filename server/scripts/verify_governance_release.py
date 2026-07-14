"""Verify SOIT 1.1 governance release evidence."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

EXPECTED_RELEASE = "v1.1.0"
EXPECTED_DEMO_SCENARIO = "governance_demo_20_min"
COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_RELEASE_COMMANDS = {"git_tag", "release_notes_publication"}


class GovernanceReleaseEvidenceError(ValueError):
    """Raised when governance release evidence is incomplete or inconsistent."""


def load_evidence(path: Path) -> dict[str, Any]:
    """Load a governance release evidence JSON document."""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise GovernanceReleaseEvidenceError("evidence document must be a JSON object")
    return data


def _require_mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise GovernanceReleaseEvidenceError(f"{key} must be an object")
    return value


def _require_string(parent: dict[str, Any], key: str, *, section: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GovernanceReleaseEvidenceError(f"{section}.{key} must be a non-empty string")
    return value.strip()


def _require_bool(parent: dict[str, Any], key: str, *, section: str) -> bool:
    value = parent.get(key)
    if not isinstance(value, bool):
        raise GovernanceReleaseEvidenceError(f"{section}.{key} must be a boolean")
    return value


def _require_passed_records(parent: dict[str, Any], key: str, *, section: str) -> list[dict[str, Any]]:
    records = parent.get(key)
    if not isinstance(records, list) or not records:
        raise GovernanceReleaseEvidenceError(f"{section}.{key} must be a non-empty list")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise GovernanceReleaseEvidenceError(f"{section}.{key}[{index}] must be an object")
        if record.get("exit_code") != 0 and record.get("passed") is not True:
            raise GovernanceReleaseEvidenceError(f"{section}.{key}[{index}] did not pass")
        _require_string(record, "command", section=f"{section}.{key}[{index}]")
    return records


def _validate_governance_demo(evidence: dict[str, Any]) -> str:
    demo = _require_mapping(evidence, "governance_demo")
    scenario = _require_string(demo, "scenario", section="governance_demo")
    if scenario != EXPECTED_DEMO_SCENARIO:
        raise GovernanceReleaseEvidenceError(
            f"governance_demo.scenario {scenario!r} does not match {EXPECTED_DEMO_SCENARIO!r}"
        )
    if _require_bool(demo, "passed", section="governance_demo") is not True:
        raise GovernanceReleaseEvidenceError("governance_demo.passed must be true")
    _require_string(demo, "report_path", section="governance_demo")
    sections = demo.get("sections")
    required_sections = {
        "permissions",
        "secrets",
        "call_audit",
        "cost_attribution",
        "replay",
        "regression",
    }
    if not isinstance(sections, list):
        raise GovernanceReleaseEvidenceError("governance_demo.sections must be a list")
    if len(set(sections)) != len(sections):
        raise GovernanceReleaseEvidenceError("duplicate governance demo section")
    if set(sections) != required_sections:
        raise GovernanceReleaseEvidenceError(
            "governance_demo.sections must cover permissions, secrets, call_audit, "
            "cost_attribution, replay, and regression"
        )
    _require_passed_records({"commands": [demo]}, "commands", section="governance_demo")
    return scenario


def validate_governance_release_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Validate SOIT 1.1 governance release evidence."""
    release = _require_string(evidence, "release", section="root")
    if release != EXPECTED_RELEASE:
        raise GovernanceReleaseEvidenceError(
            f"release {release!r} does not match {EXPECTED_RELEASE!r}"
        )
    release_tag = _require_string(evidence, "release_tag", section="root")
    if release_tag != release:
        raise GovernanceReleaseEvidenceError(
            f"release_tag {release_tag!r} does not match release {release!r}"
        )
    commit = _require_string(evidence, "commit", section="root")
    if not COMMIT_SHA_RE.fullmatch(commit) or set(commit) == {"0"}:
        raise GovernanceReleaseEvidenceError(
            "root.commit must be a non-zero 40-character lowercase git SHA"
        )
    _require_string(evidence, "release_notes", section="root")
    if _require_bool(evidence, "clean_worktree_at_tag", section="root") is not True:
        raise GovernanceReleaseEvidenceError("clean_worktree_at_tag must be true")

    scenario = _validate_governance_demo(evidence)
    _require_passed_records(evidence, "quality_gates", section="root")
    _require_passed_records(evidence, "builds", section="root")
    _validate_release_commands(evidence, release_tag=release_tag, commit=commit)

    return {
        "passed": True,
        "release": release,
        "release_tag": release_tag,
        "governance_demo": scenario,
    }


def _validate_release_commands(
    evidence: dict[str, Any],
    *,
    release_tag: str,
    commit: str,
) -> None:
    commands = _require_passed_records(evidence, "release_commands", section="root")
    named_commands: dict[str, dict[str, Any]] = {}
    for index, command in enumerate(commands):
        name = _require_string(command, "name", section=f"root.release_commands[{index}]")
        if name in named_commands:
            raise GovernanceReleaseEvidenceError(f"duplicate release command: {name}")
        named_commands[name] = command

    missing = REQUIRED_RELEASE_COMMANDS - set(named_commands)
    if missing:
        raise GovernanceReleaseEvidenceError(f"root.release_commands missing required records: {sorted(missing)}")

    tag_command = named_commands["git_tag"]
    tag = _require_string(tag_command, "tag", section="root.release_commands.git_tag")
    if tag != release_tag:
        raise GovernanceReleaseEvidenceError("root.release_commands.git_tag.tag must match release_tag")
    tag_commit = _require_string(tag_command, "commit", section="root.release_commands.git_tag")
    if tag_commit != commit:
        raise GovernanceReleaseEvidenceError("root.release_commands.git_tag.commit must match root.commit")
    _require_string(tag_command, "evidence_ref", section="root.release_commands.git_tag")

    publication_command = named_commands["release_notes_publication"]
    release_url = _require_string(
        publication_command,
        "release_url",
        section="root.release_commands.release_notes_publication",
    )
    if not release_url.startswith("https://") or release_tag not in release_url:
        raise GovernanceReleaseEvidenceError(
            "root.release_commands.release_notes_publication.release_url must be an HTTPS URL for release_tag"
        )
    _require_string(
        publication_command,
        "evidence_ref",
        section="root.release_commands.release_notes_publication",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify SOIT 1.1 governance release evidence.")
    parser.add_argument("evidence", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        report = validate_governance_release_evidence(load_evidence(args.evidence))
    except GovernanceReleaseEvidenceError as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
