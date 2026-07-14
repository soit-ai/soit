"""Verify SOIT 1.0 release evidence."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

EXPECTED_RELEASE = "v1.0.0"
COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_EVIDENCE = {
    "quickstart_deployment",
    "manual_acceptance",
    "model_provider_spotcheck",
    "migration_paths",
    "non_developer_feedback",
    "quality_gate",
    "release_notes_published",
}


class Phase1ReleaseEvidenceError(ValueError):
    """Raised when SOIT 1.0 release evidence is incomplete or inconsistent."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="Path to SOIT 1.0 release evidence JSON")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root used to require local evidence refs and validate the release tag",
    )
    args = parser.parse_args()

    evidence = load_evidence(args.evidence)
    report = validate_phase1_release_evidence(evidence, repo_root=args.repo_root)
    print(f"phase1 release evidence verified: {report['release']}")
    return 0


def load_evidence(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise Phase1ReleaseEvidenceError("evidence must be a JSON object")
    return payload


def validate_phase1_release_evidence(
    evidence: dict[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    release = _require_text(evidence, "release")
    if release != EXPECTED_RELEASE:
        raise Phase1ReleaseEvidenceError(f"release must be {EXPECTED_RELEASE}")
    release_tag = _require_text(evidence, "release_tag")
    if release_tag != release:
        raise Phase1ReleaseEvidenceError("release_tag must match release")
    commit = _require_text(evidence, "commit")
    if not COMMIT_SHA_RE.fullmatch(commit) or set(commit) == {"0"}:
        raise Phase1ReleaseEvidenceError("commit must be a non-zero 40-character lowercase git SHA")
    release_notes = _require_text(evidence, "release_notes")
    _require_text(evidence, "operator")
    _parse_timestamp(_require_text(evidence, "publishedAt"), "publishedAt")
    if evidence.get("clean_worktree_at_tag") is not True:
        raise Phase1ReleaseEvidenceError("clean_worktree_at_tag must be true")

    records = evidence.get("evidence")
    if not isinstance(records, list):
        raise Phase1ReleaseEvidenceError("evidence must be a list")
    records_by_name: dict[str, dict[str, Any]] = {}
    evidence_refs: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise Phase1ReleaseEvidenceError("evidence entries must be objects")
        name = _require_text(record, "name")
        if name in records_by_name:
            raise Phase1ReleaseEvidenceError(f"duplicate evidence record: {name}")
        evidence_ref = _require_text(record, "evidenceRef")
        if evidence_ref in evidence_refs:
            raise Phase1ReleaseEvidenceError(f"duplicate evidenceRef: {evidence_ref}")
        evidence_refs.add(evidence_ref)
        records_by_name[name] = record
    missing = REQUIRED_EVIDENCE - set(records_by_name)
    if missing:
        raise Phase1ReleaseEvidenceError(f"missing evidence records: {sorted(missing)}")
    for name in REQUIRED_EVIDENCE:
        _require_passed_evidence(records_by_name[name], f"evidence.{name}")
    if repo_root is not None:
        _require_existing_ref(release_notes, repo_root=repo_root, key="release_notes")
        for name in REQUIRED_EVIDENCE:
            _require_existing_ref(
                _require_text(records_by_name[name], "evidenceRef"),
                repo_root=repo_root,
                key="evidenceRef",
            )
        _require_matching_release_tag(
            release_tag=release_tag,
            commit=commit,
            repo_root=repo_root,
        )

    return {
        "passed": True,
        "release": release,
        "release_tag": release_tag,
    }


def _require_passed_evidence(payload: Any, path: str) -> None:
    if not isinstance(payload, dict):
        raise Phase1ReleaseEvidenceError(f"{path} must be an object")
    if payload.get("status") != "passed":
        raise Phase1ReleaseEvidenceError(f"{path}.status must be passed")
    _require_text(payload, "evidenceRef")


def _require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise Phase1ReleaseEvidenceError(f"{key} must be a non-empty string")
    return value.strip()


def _parse_timestamp(value: str, key: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise Phase1ReleaseEvidenceError(f"{key} must be an ISO timestamp") from exc


def _require_existing_ref(evidence_ref: str, *, repo_root: Path, key: str) -> None:
    if "://" in evidence_ref or evidence_ref.startswith("local-http:"):
        raise Phase1ReleaseEvidenceError(f"{key} must be repository-relative: {evidence_ref}")
    path = (repo_root / evidence_ref).resolve()
    repo = repo_root.resolve()
    if repo not in (path, *path.parents):
        raise Phase1ReleaseEvidenceError(f"{key} escapes repository root: {evidence_ref}")
    if not path.is_file():
        raise Phase1ReleaseEvidenceError(f"{key} does not exist: {evidence_ref}")


def _require_matching_release_tag(*, release_tag: str, commit: str, repo_root: Path) -> None:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "rev-parse",
            "--verify",
            f"refs/tags/{release_tag}^{{commit}}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise Phase1ReleaseEvidenceError(f"release_tag does not exist: {release_tag}")
    tagged_commit = result.stdout.strip()
    if tagged_commit != commit:
        raise Phase1ReleaseEvidenceError(
            f"release_tag {release_tag} points to {tagged_commit}, expected {commit}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
