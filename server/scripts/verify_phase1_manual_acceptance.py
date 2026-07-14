"""Verify SOIT 1.0 manual UI and Chain A/B acceptance evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

REQUIRED_ROUTES = {
    "/",
    "/models",
    "/knowledge",
    "/agents",
    "/chat",
    "/observe/runs",
    "/workflow",
    "/tasks",
    "/settings",
}
REQUIRED_CHAINS = {"chain_a", "chain_b"}
REQUIRED_VIEWPORTS = {"desktop", "mobile"}


class ManualAcceptanceEvidenceError(ValueError):
    """Raised when Phase 1 manual acceptance evidence is incomplete or invalid."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="Path to Phase 1 manual acceptance evidence JSON")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root used to require local evidenceRef files",
    )
    args = parser.parse_args()

    evidence = load_evidence(args.evidence)
    report = validate_manual_acceptance_evidence(evidence, repo_root=args.repo_root)
    print(f"phase1 manual acceptance evidence verified: {report['acceptance_id']}")
    return 0


def load_evidence(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ManualAcceptanceEvidenceError("evidence must be a JSON object")
    return payload


def validate_manual_acceptance_evidence(
    evidence: dict[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    if evidence.get("featureKey") != "phase1.manual_acceptance":
        raise ManualAcceptanceEvidenceError("featureKey must be phase1.manual_acceptance")

    for key in ("acceptanceId", "release", "environment", "reviewer"):
        _require_text(evidence, key)
    started_at = _parse_timestamp(_require_text(evidence, "startedAt"))
    finished_at = _parse_timestamp(_require_text(evidence, "finishedAt"))
    if finished_at <= started_at:
        raise ManualAcceptanceEvidenceError("finishedAt must be after startedAt")

    owner_ui = evidence.get("owner_ui_spotcheck")
    if not isinstance(owner_ui, dict):
        raise ManualAcceptanceEvidenceError("owner_ui_spotcheck must be an object")
    if owner_ui.get("result") != "Pass":
        raise ManualAcceptanceEvidenceError("owner_ui_spotcheck.result must be Pass")
    _require_text(owner_ui, "checklistRef")
    _require_text(owner_ui, "signedRecordRef")

    route_results = owner_ui.get("routeResults")
    if not isinstance(route_results, list):
        raise ManualAcceptanceEvidenceError("owner_ui_spotcheck.routeResults must be a list")
    routes_by_path: dict[str, dict[str, Any]] = {}
    for route in route_results:
        if not isinstance(route, dict):
            raise ManualAcceptanceEvidenceError("routeResults entries must be objects")
        path = _require_text(route, "path")
        if path in routes_by_path:
            raise ManualAcceptanceEvidenceError(f"duplicate route result: {path}")
        routes_by_path[path] = route
    missing_routes = REQUIRED_ROUTES - set(routes_by_path)
    if missing_routes:
        raise ManualAcceptanceEvidenceError(f"missing owner UI routes: {sorted(missing_routes)}")
    route_evidence_refs: set[str] = set()
    for path in REQUIRED_ROUTES:
        _require_passed_evidence(routes_by_path[path], f"owner_ui_spotcheck.routeResults.{path}")
        _require_unique_evidence_ref(
            route_evidence_refs,
            routes_by_path[path],
            f"owner_ui_spotcheck.routeResults.{path}",
        )
        _require_viewports(routes_by_path[path], f"owner_ui_spotcheck.routeResults.{path}", path)

    chain_results = evidence.get("chainResults")
    if not isinstance(chain_results, list):
        raise ManualAcceptanceEvidenceError("chainResults must be a list")
    chains_by_name: dict[str, dict[str, Any]] = {}
    for chain in chain_results:
        if not isinstance(chain, dict):
            raise ManualAcceptanceEvidenceError("chainResults entries must be objects")
        name = _require_text(chain, "name")
        if name in chains_by_name:
            raise ManualAcceptanceEvidenceError(f"duplicate chain result: {name}")
        chains_by_name[name] = chain
    missing_chains = REQUIRED_CHAINS - set(chains_by_name)
    if missing_chains:
        raise ManualAcceptanceEvidenceError(f"missing chain acceptance results: {sorted(missing_chains)}")
    chain_evidence_refs: set[str] = set()
    for name in REQUIRED_CHAINS:
        _require_passed_evidence(chains_by_name[name], f"chainResults.{name}")
        _require_unique_evidence_ref(chain_evidence_refs, chains_by_name[name], f"chainResults.{name}")

    if repo_root is not None:
        _require_existing_ref(_require_text(owner_ui, "signedRecordRef"), repo_root=repo_root)
        for route in [routes_by_path[path] for path in REQUIRED_ROUTES]:
            _require_existing_ref(_require_text(route, "evidenceRef"), repo_root=repo_root)
            for viewport in route["viewports"]:
                _require_existing_ref(_require_text(viewport, "evidenceRef"), repo_root=repo_root)
        for chain in [chains_by_name[name] for name in REQUIRED_CHAINS]:
            _require_existing_ref(_require_text(chain, "evidenceRef"), repo_root=repo_root)

    return {
        "passed": True,
        "acceptance_id": evidence["acceptanceId"],
        "route_count": len(REQUIRED_ROUTES),
        "chains": sorted(REQUIRED_CHAINS),
    }


def _require_passed_evidence(payload: Any, path: str) -> None:
    if not isinstance(payload, dict):
        raise ManualAcceptanceEvidenceError(f"{path} must be an object")
    if payload.get("status") != "passed":
        raise ManualAcceptanceEvidenceError(f"{path}.status must be passed")
    _require_text(payload, "evidenceRef")


def _require_viewports(route: dict[str, Any], path: str, route_path: str) -> None:
    viewports = route.get("viewports")
    if not isinstance(viewports, list):
        raise ManualAcceptanceEvidenceError(f"{path}.viewports must be a list")
    viewports_by_name: dict[str, dict[str, Any]] = {}
    for viewport in viewports:
        if not isinstance(viewport, dict):
            raise ManualAcceptanceEvidenceError(f"{path}.viewports entries must be objects")
        name = _require_text(viewport, "name")
        if name in viewports_by_name:
            raise ManualAcceptanceEvidenceError(f"{path}.duplicate viewport: {name}")
        viewports_by_name[name] = viewport
    missing = REQUIRED_VIEWPORTS - set(viewports_by_name)
    if missing:
        raise ManualAcceptanceEvidenceError(f"{route_path} missing viewport evidence: {sorted(missing)}")
    viewport_evidence_refs: set[str] = set()
    for name in REQUIRED_VIEWPORTS:
        _require_passed_evidence(viewports_by_name[name], f"{path}.viewports.{name}")
        _require_unique_evidence_ref(viewport_evidence_refs, viewports_by_name[name], f"{path}.viewports.{name}")


def _require_unique_evidence_ref(seen: set[str], payload: dict[str, Any], path: str) -> None:
    evidence_ref = _require_text(payload, "evidenceRef")
    if evidence_ref in seen:
        raise ManualAcceptanceEvidenceError(f"{path} duplicate evidenceRef: {evidence_ref}")
    seen.add(evidence_ref)


def _require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManualAcceptanceEvidenceError(f"{key} must be a non-empty string")
    return value.strip()


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ManualAcceptanceEvidenceError(f"invalid ISO timestamp: {value}") from exc


def _require_existing_ref(evidence_ref: str, *, repo_root: Path) -> None:
    if "://" in evidence_ref or evidence_ref.startswith("local-http:"):
        raise ManualAcceptanceEvidenceError(f"evidenceRef must be repository-relative: {evidence_ref}")
    ref_path = evidence_ref.split("#", 1)[0]
    path = (repo_root / ref_path).resolve()
    repo = repo_root.resolve()
    if repo not in (path, *path.parents):
        raise ManualAcceptanceEvidenceError(f"evidenceRef escapes repository root: {evidence_ref}")
    if not path.is_file():
        raise ManualAcceptanceEvidenceError(f"evidenceRef does not exist: {evidence_ref}")


if __name__ == "__main__":
    raise SystemExit(main())
