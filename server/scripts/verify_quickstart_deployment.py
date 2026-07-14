"""Verify SOIT 1.0 Quickstart deployment evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

REQUIRED_SERVICES = {
    "postgres",
    "redis",
    "minio",
    "etcd",
    "milvus",
    "vault",
    "migrate",
    "bootstrap",
    "api",
    "web",
    "knowledge-ingest-worker",
}


class QuickstartDeploymentEvidenceError(ValueError):
    """Raised when Quickstart deployment evidence is incomplete or invalid."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="Path to Quickstart deployment evidence JSON")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root used to require local evidenceRef files",
    )
    args = parser.parse_args()

    evidence = load_evidence(args.evidence)
    report = validate_quickstart_deployment(evidence, repo_root=args.repo_root)
    print(f"quickstart deployment evidence verified: {report['deployment_id']}")
    return 0


def load_evidence(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise QuickstartDeploymentEvidenceError("evidence must be a JSON object")
    return payload


def validate_quickstart_deployment(
    evidence: dict[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    if evidence.get("featureKey") != "phase1.quickstart_deployment":
        raise QuickstartDeploymentEvidenceError("featureKey must be phase1.quickstart_deployment")

    for key in ("deploymentId", "release", "environment", "operator"):
        _require_text(evidence, key)
    started_at = _parse_timestamp(_require_text(evidence, "startedAt"))
    finished_at = _parse_timestamp(_require_text(evidence, "finishedAt"))
    if finished_at <= started_at:
        raise QuickstartDeploymentEvidenceError("finishedAt must be after startedAt")

    docker = evidence.get("docker")
    if not isinstance(docker, dict):
        raise QuickstartDeploymentEvidenceError("docker must be an object")
    elapsed = docker.get("elapsedSeconds")
    if not isinstance(elapsed, int) or elapsed <= 0:
        raise QuickstartDeploymentEvidenceError("docker.elapsedSeconds must be a positive integer")
    if elapsed > 600:
        raise QuickstartDeploymentEvidenceError("docker.elapsedSeconds must be within 10 minutes")
    _require_text(docker, "composeCommand")
    compose_ps_evidence_ref = _require_text(docker, "composePsEvidenceRef")

    services = docker.get("services")
    if not isinstance(services, list):
        raise QuickstartDeploymentEvidenceError("docker.services must be a list")
    services_by_name: dict[str, dict[str, Any]] = {}
    for service in services:
        if not isinstance(service, dict):
            raise QuickstartDeploymentEvidenceError("docker.services entries must be objects")
        name = _require_text(service, "name")
        if name in services_by_name:
            raise QuickstartDeploymentEvidenceError(f"duplicate docker service: {name}")
        services_by_name[name] = service
    missing = REQUIRED_SERVICES - set(services_by_name)
    if missing:
        raise QuickstartDeploymentEvidenceError(f"missing docker services: {sorted(missing)}")
    for name in REQUIRED_SERVICES:
        if services_by_name[name].get("status") != "running":
            raise QuickstartDeploymentEvidenceError(f"docker.services.{name}.status must be running")
        if services_by_name[name].get("health") != "healthy":
            raise QuickstartDeploymentEvidenceError(f"docker.services.{name}.health must be healthy")
        if not isinstance(services_by_name[name].get("evidenceRef"), str) or not services_by_name[name]["evidenceRef"].strip():
            raise QuickstartDeploymentEvidenceError(
                f"docker.services.{name}.evidenceRef must be a non-empty string"
            )
        _require_text(services_by_name[name], "evidenceRef")
    _require_unique_evidence_refs(
        [services_by_name[name] for name in REQUIRED_SERVICES],
        "docker.services",
    )

    checks = evidence.get("checks")
    if not isinstance(checks, dict):
        raise QuickstartDeploymentEvidenceError("checks must be an object")
    for key in ("apiHealth", "webHealth", "knowledgeWorker", "demoSeed", "chainA", "regression"):
        check = checks.get(key)
        if not isinstance(check, dict):
            raise QuickstartDeploymentEvidenceError(f"checks.{key} must be an object")
        if check.get("status") != "passed":
            raise QuickstartDeploymentEvidenceError(f"checks.{key}.status must be passed")
        _require_text(check, "evidenceRef")
    _require_unique_evidence_refs(
        [checks[key] for key in ("apiHealth", "webHealth", "knowledgeWorker", "demoSeed", "chainA", "regression")],
        "checks",
    )
    if repo_root is not None:
        _require_existing_ref(compose_ps_evidence_ref, repo_root=repo_root)
        for record in [services_by_name[name] for name in REQUIRED_SERVICES]:
            _require_existing_ref(_require_text(record, "evidenceRef"), repo_root=repo_root)
        for record in [checks[key] for key in ("apiHealth", "webHealth", "knowledgeWorker", "demoSeed", "chainA", "regression")]:
            _require_existing_ref(_require_text(record, "evidenceRef"), repo_root=repo_root)

    return {
        "passed": True,
        "deployment_id": evidence["deploymentId"],
        "elapsed_seconds": elapsed,
        "chain_a": checks["chainA"]["status"],
    }


def _require_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise QuickstartDeploymentEvidenceError(f"{key} must be a non-empty string")
    return value.strip()


def _require_unique_evidence_refs(records: list[dict[str, Any]], path: str) -> None:
    evidence_refs: set[str] = set()
    for record in records:
        evidence_ref = _require_text(record, "evidenceRef")
        if evidence_ref in evidence_refs:
            raise QuickstartDeploymentEvidenceError(f"{path} duplicate evidenceRef: {evidence_ref}")
        evidence_refs.add(evidence_ref)


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise QuickstartDeploymentEvidenceError(f"invalid ISO timestamp: {value}") from exc


def _require_existing_ref(evidence_ref: str, *, repo_root: Path) -> None:
    if "://" in evidence_ref or evidence_ref.startswith("local-http:"):
        raise QuickstartDeploymentEvidenceError(
            f"evidenceRef must be repository-relative: {evidence_ref}"
        )
    path = (repo_root / evidence_ref).resolve()
    repo = repo_root.resolve()
    if repo not in (path, *path.parents):
        raise QuickstartDeploymentEvidenceError(f"evidenceRef escapes repository root: {evidence_ref}")
    if not path.is_file():
        raise QuickstartDeploymentEvidenceError(f"evidenceRef does not exist: {evidence_ref}")


if __name__ == "__main__":
    raise SystemExit(main())
