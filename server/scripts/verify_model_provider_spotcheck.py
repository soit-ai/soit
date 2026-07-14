"""Verify SOIT 1.0 live model provider spot-check evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

KNOWN_PROVIDERS = {"openai", "openai-compatible", "deepseek", "anthropic", "gemini"}


class ModelProviderSpotcheckEvidenceError(ValueError):
    """Raised when live model provider spot-check evidence is incomplete or invalid."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="Path to model provider spot-check evidence JSON")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root used to require local evidenceRef files",
    )
    args = parser.parse_args()

    evidence = load_evidence(args.evidence)
    report = validate_model_provider_spotcheck(evidence, repo_root=args.repo_root)
    print(f"model provider spot-check evidence verified: {report['spotcheck_id']}")
    return 0


def load_evidence(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ModelProviderSpotcheckEvidenceError("evidence must be a JSON object")
    return payload


def validate_model_provider_spotcheck(
    evidence: dict[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    if evidence.get("featureKey") != "modelhub.provider_spotcheck":
        raise ModelProviderSpotcheckEvidenceError("featureKey must be modelhub.provider_spotcheck")

    for key in ("spotcheckId", "release", "environment", "operator"):
        _require_text(evidence, key)
    started_at = _parse_timestamp(_require_text(evidence, "startedAt"))
    finished_at = _parse_timestamp(_require_text(evidence, "finishedAt"))
    if finished_at <= started_at:
        raise ModelProviderSpotcheckEvidenceError("finishedAt must be after startedAt")

    providers = evidence.get("providers")
    if not isinstance(providers, list):
        raise ModelProviderSpotcheckEvidenceError("providers must be a list")

    providers_by_key: dict[str, dict[str, Any]] = {}
    evidence_refs: set[str] = set()
    for provider in providers:
        if not isinstance(provider, dict):
            raise ModelProviderSpotcheckEvidenceError("providers entries must be objects")
        key = _require_text(provider, "providerKey").lower()
        if key not in KNOWN_PROVIDERS:
            raise ModelProviderSpotcheckEvidenceError(f"unknown providerKey: {key}")
        if key in providers_by_key:
            raise ModelProviderSpotcheckEvidenceError(f"duplicate providerKey: {key}")
        if provider.get("status") != "passed":
            raise ModelProviderSpotcheckEvidenceError(f"providers.{key}.status must be passed")
        for field in (
            "credentialRef",
            "modelRef",
            "diagnosticsEvidenceRef",
            "chatCompletionEvidenceRef",
            "costAttributionEvidenceRef",
        ):
            evidence_ref = _require_text(provider, field)
            if evidence_ref in evidence_refs:
                raise ModelProviderSpotcheckEvidenceError(f"duplicate evidenceRef: {evidence_ref}")
            evidence_refs.add(evidence_ref)
        providers_by_key[key] = provider

    if len(providers_by_key) < 2:
        raise ModelProviderSpotcheckEvidenceError("at least 2 provider spot-check records are required")

    if repo_root is not None:
        for provider in providers_by_key.values():
            for field in (
                "diagnosticsEvidenceRef",
                "chatCompletionEvidenceRef",
                "costAttributionEvidenceRef",
            ):
                _require_existing_ref(_require_text(provider, field), repo_root=repo_root)

    return {
        "passed": True,
        "spotcheck_id": evidence["spotcheckId"],
        "provider_count": len(providers_by_key),
        "providers": sorted(providers_by_key),
    }


def _require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ModelProviderSpotcheckEvidenceError(f"{key} must be a non-empty string")
    return value.strip()


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ModelProviderSpotcheckEvidenceError(f"invalid ISO timestamp: {value}") from exc


def _require_existing_ref(evidence_ref: str, *, repo_root: Path) -> None:
    if "://" in evidence_ref or evidence_ref.startswith("local-http:"):
        raise ModelProviderSpotcheckEvidenceError(
            f"evidenceRef must be repository-relative: {evidence_ref}"
        )
    ref_path = evidence_ref.split("#", 1)[0]
    path = (repo_root / ref_path).resolve()
    repo = repo_root.resolve()
    if repo not in (path, *path.parents):
        raise ModelProviderSpotcheckEvidenceError(f"evidenceRef escapes repository root: {evidence_ref}")
    if not path.is_file():
        raise ModelProviderSpotcheckEvidenceError(f"evidenceRef does not exist: {evidence_ref}")


if __name__ == "__main__":
    raise SystemExit(main())
