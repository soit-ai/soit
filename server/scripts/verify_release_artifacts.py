"""Validate a SOIT Community release artifact evidence document."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REQUIRED_IMAGES = {"server", "knowledge-worker", "web"}


class ReleaseArtifactEvidenceError(ValueError):
    """Raised when release artifacts are incomplete or not bound together."""


def load_release_artifact_evidence(path: Path) -> dict[str, Any]:
    """Load a release artifact evidence JSON document."""

    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ReleaseArtifactEvidenceError("release artifact evidence must be a JSON object")
    return payload


def validate_release_artifact_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Validate tag/version/commit, digest-pinned images, SBOMs, and provenance."""

    if evidence.get("featureKey") != "release.artifacts":
        raise ReleaseArtifactEvidenceError("featureKey must be release.artifacts")
    if evidence.get("schemaVersion") != 1:
        raise ReleaseArtifactEvidenceError("schemaVersion must be 1")

    version = _require_text(evidence, "version", "root")
    release_tag = _require_text(evidence, "release_tag", "root")
    if release_tag != f"v{version}":
        raise ReleaseArtifactEvidenceError("release_tag must equal v{version}")
    commit = _require_text(evidence, "commit", "root")
    if not COMMIT_RE.fullmatch(commit) or set(commit) == {"0"}:
        raise ReleaseArtifactEvidenceError(
            "commit must be a non-zero 40-character lowercase git SHA"
        )
    if evidence.get("clean_worktree_at_tag") is not True:
        raise ReleaseArtifactEvidenceError("clean_worktree_at_tag must be true")
    _require_text(evidence, "release_url", "root")
    _require_text(evidence, "release_notes", "root")
    _parse_timestamp(_require_text(evidence, "publishedAt", "root"), "publishedAt")

    source = _require_mapping(evidence, "source_archive", "root")
    _require_text(source, "path", "source_archive")
    _require_sha256(source, "sha256", "source_archive")
    _require_text(source, "provenance_attestation", "source_archive")

    checksums = _require_mapping(evidence, "checksums", "root")
    if _require_text(checksums, "path", "checksums") != "SHA256SUMS":
        raise ReleaseArtifactEvidenceError("checksums.path must be SHA256SUMS")
    _require_sha256(checksums, "sha256", "checksums")
    _require_text(checksums, "provenance_attestation", "checksums")

    images = evidence.get("images")
    if not isinstance(images, list):
        raise ReleaseArtifactEvidenceError("images must be a list")
    components: set[str] = set()
    image_names: set[str] = set()
    evidence_refs = {
        source["provenance_attestation"],
        checksums["provenance_attestation"],
    }
    for index, image in enumerate(images):
        section = f"images[{index}]"
        if not isinstance(image, dict):
            raise ReleaseArtifactEvidenceError(f"{section} must be an object")
        component = _require_text(image, "component", section)
        if component in components:
            raise ReleaseArtifactEvidenceError(f"duplicate image component: {component}")
        components.add(component)
        name = _require_text(image, "name", section)
        if name in image_names:
            raise ReleaseArtifactEvidenceError(f"duplicate image name: {name}")
        image_names.add(name)
        digest = _require_text(image, "digest", section)
        if not DIGEST_RE.fullmatch(digest):
            raise ReleaseArtifactEvidenceError(f"{section}.digest must be sha256:<64 hex>")
        reference = _require_text(image, "reference", section)
        if reference != f"{name}@{digest}":
            raise ReleaseArtifactEvidenceError(
                f"{section}.reference must be digest-pinned to name@digest"
            )
        if image.get("release_tag") != release_tag:
            raise ReleaseArtifactEvidenceError(f"{section}.release_tag must match release_tag")

        sbom = _require_mapping(image, "sbom", section)
        if sbom.get("format") != "spdx-json":
            raise ReleaseArtifactEvidenceError(f"{section}.sbom.format must be spdx-json")
        _require_text(sbom, "path", f"{section}.sbom")
        _require_sha256(sbom, "sha256", f"{section}.sbom")
        sbom_attestation = _require_text(
            sbom, "attestation", f"{section}.sbom"
        )
        provenance = _require_text(image, "provenance_attestation", section)
        for evidence_ref in (sbom_attestation, provenance):
            if evidence_ref in evidence_refs:
                raise ReleaseArtifactEvidenceError(
                    f"duplicate attestation reference: {evidence_ref}"
                )
            evidence_refs.add(evidence_ref)

    if components != REQUIRED_IMAGES:
        raise ReleaseArtifactEvidenceError(
            f"images must contain exactly {sorted(REQUIRED_IMAGES)}"
        )

    return {
        "passed": True,
        "release_tag": release_tag,
        "commit": commit,
        "images": sorted(components),
    }


def _require_mapping(parent: dict[str, Any], key: str, section: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise ReleaseArtifactEvidenceError(f"{section}.{key} must be an object")
    return value


def _require_text(parent: dict[str, Any], key: str, section: str) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReleaseArtifactEvidenceError(f"{section}.{key} must be a non-empty string")
    return value.strip()


def _require_sha256(parent: dict[str, Any], key: str, section: str) -> str:
    value = _require_text(parent, key, section)
    if not SHA256_RE.fullmatch(value):
        raise ReleaseArtifactEvidenceError(f"{section}.{key} must be lowercase SHA256")
    return value


def _parse_timestamp(value: str, key: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReleaseArtifactEvidenceError(f"{key} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ReleaseArtifactEvidenceError(f"{key} must include a timezone")
    return parsed


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        report = validate_release_artifact_evidence(
            load_release_artifact_evidence(args.evidence)
        )
    except ReleaseArtifactEvidenceError as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
