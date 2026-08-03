"""Backup/restore and release supply-chain contract tests."""

from __future__ import annotations

import importlib
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.verify_backup_manifest import (
    BackupManifestError,
    load_backup_manifest,
    validate_backup_manifest,
)
from scripts.verify_release_artifacts import (
    ReleaseArtifactEvidenceError,
    load_release_artifact_evidence,
    validate_release_artifact_evidence,
)
from scripts.verify_restore_drill import (
    RestoreDrillEvidenceError,
    load_restore_drill_evidence,
    validate_restore_drill_evidence,
)
from scripts.verify_vulnerability_exceptions import (
    VulnerabilityExceptionError,
    validate_vulnerability_exceptions,
)

ROOT = Path(__file__).resolve().parents[3]


def test_backup_manifest_example_is_machine_verifiable() -> None:
    evidence = load_backup_manifest(
        ROOT / "docs" / "deployment" / "backup-manifest.example.json"
    )

    report = validate_backup_manifest(evidence)

    assert report == {
        "passed": True,
        "backup_id": "backup_example_20260723T160000Z",
        "alembic_revision": "20260803090000",
        "file_count": 3,
    }

    broken = deepcopy(evidence)
    broken["components"]["secret_metadata"]["secret_values_included"] = True
    with pytest.raises(BackupManifestError, match="secret values"):
        validate_backup_manifest(broken)


def test_restore_drill_example_requires_all_canonical_and_derived_checks() -> None:
    evidence = load_restore_drill_evidence(
        ROOT / "docs" / "deployment" / "restore-drill-evidence.example.json"
    )

    report = validate_restore_drill_evidence(evidence)

    assert report["passed"] is True
    assert report["rpo_minutes"] <= report["rpo_target_minutes"]
    assert report["rto_minutes"] <= report["rto_target_minutes"]

    broken = deepcopy(evidence)
    broken["components"]["vector_index"]["query_readback_passed"] = False
    with pytest.raises(RestoreDrillEvidenceError, match="vector_index"):
        validate_restore_drill_evidence(broken)


def test_release_artifact_example_binds_tag_commit_images_and_attestations() -> None:
    evidence = load_release_artifact_evidence(
        ROOT / "docs" / "deployment" / "release-artifacts.example.json"
    )

    report = validate_release_artifact_evidence(evidence)

    assert report == {
        "passed": True,
        "release_tag": "v1.0.0",
        "commit": "0123456789abcdef0123456789abcdef01234567",
        "images": ["knowledge-worker", "server", "web"],
    }

    broken = deepcopy(evidence)
    broken["images"][0]["reference"] = "ghcr.io/soit-ai/soit/server:v1.0.0"
    with pytest.raises(ReleaseArtifactEvidenceError, match="digest-pinned"):
        validate_release_artifact_evidence(broken)


def test_release_workflow_builds_a_complete_attested_default_topology() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    required_terms = [
        "tags:",
        "v*.*.*",
        "docker/build-push-action",
        "server/Dockerfile",
        "web/Dockerfile",
        "knowledge-worker",
        "anchore/sbom-action",
        "actions/attest@v4",
        "sbom-path:",
        "push-to-registry: true",
        "SHA256SUMS",
        "gh release create",
        "git diff --exit-code",
    ]
    for term in required_terms:
        assert term in workflow


def test_publication_security_and_license_gates_are_explicit() -> None:
    security_policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    security_workflow = (
        ROOT / ".github" / "workflows" / "security.yml"
    ).read_text(encoding="utf-8")
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")

    assert "private vulnerability reporting" in security_policy.lower()
    assert "supported versions" in security_policy.lower()
    assert "gitleaks" in security_workflow.lower()
    assert "trivy" in security_workflow.lower()
    assert "CRITICAL,HIGH" in security_workflow
    assert "vulnerability-exceptions.json" in security_workflow
    assert "license" in security_workflow.lower()
    assert "uv run pyright" in contributing
    assert "uv run mypy" not in contributing


def test_quality_workflow_has_explicit_postgres_and_security_gates() -> None:
    workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text(
        encoding="utf-8"
    )
    quality_doc = (ROOT / "docs" / "QUALITY_GATE.md").read_text(
        encoding="utf-8"
    )

    assert "PostgreSQL runtime concurrency contracts" in workflow
    assert "uv run pytest tests/postgres -q" in workflow
    assert "Release-blocking security regressions" in workflow
    for contract in (
        "test_governed_egress_paths.py",
        "test_scoped_secrets_port.py",
        "test_resource_permissions.py",
        "test_agent_service.py",
    ):
        assert contract in workflow
    assert "A skipped PostgreSQL suite is not a passing release gate." in quality_doc


def test_quality_workflow_runs_a_real_empty_workspace_fullstack_journey() -> None:
    workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text(
        encoding="utf-8"
    )
    real_spec = (ROOT / "web" / "e2e-real" / "empty-workspace.spec.ts").read_text(
        encoding="utf-8"
    )

    for term in (
        "fullstack-real:",
        "ALLOW_PUBLIC_REGISTRATION: \"true\"",
        "Start dedicated runtime workers",
        "npm run test:e2e:real",
        "Upload real full-stack diagnostics",
    ):
        assert term in workflow

    assert "page.route(" not in real_spec
    for path in (
        "/knowledge",
        "/agents",
        "/observe/runs/",
        "/workflow",
    ):
        assert path in real_spec


def test_vulnerability_exceptions_require_owner_reason_and_expiry() -> None:
    valid = {
        "schemaVersion": 1,
        "exceptions": [
            {
                "vulnerability_id": "CVE-2099-0001",
                "owner": "security-owner",
                "reason": "No reachable vulnerable code path in the released runtime.",
                "expires_on": "2099-12-31",
            }
        ],
    }

    report = validate_vulnerability_exceptions(valid)

    assert report == {"passed": True, "exception_count": 1}

    broken = deepcopy(valid)
    broken["exceptions"][0]["owner"] = ""
    with pytest.raises(VulnerabilityExceptionError, match="owner"):
        validate_vulnerability_exceptions(broken)


def test_backup_restore_runbook_states_scope_and_recovery_limits() -> None:
    runbook = (ROOT / "docs" / "operations" / "backup-restore.md").read_text(
        encoding="utf-8"
    )

    required_terms = [
        "RPO",
        "RTO",
        "PostgreSQL",
        "object storage",
        "vector index",
        "rebuild",
        "Secret metadata",
        "Vault dev mode",
        "stop",
        "rollback",
        "verify_backup_manifest.py",
        "verify_restore_drill.py",
        "compose_backup.py",
        "compose_restore.py",
    ]
    for term in required_terms:
        assert term.lower() in runbook.lower()

    backup_tool = (
        ROOT / "docker" / "operations" / "compose_backup.py"
    ).read_text(encoding="utf-8")
    restore_tool = (
        ROOT / "docker" / "operations" / "compose_restore.py"
    ).read_text(encoding="utf-8")
    assert "pg_dump" in backup_tool
    assert "mc mirror" in backup_tool
    assert "stop application services before backup" in backup_tool
    assert "--confirm-project" in restore_tool
    assert "--confirm-database" in restore_tool
    assert "--confirm-bucket" in restore_tool
    assert "--remove" in backup_tool


def test_compose_restore_requires_exact_destructive_target_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "docker" / "operations"))
    compose_restore = importlib.import_module("compose_restore")

    compose_restore._confirm_target(
        actual_project="soit-restore-drill",
        confirmed_project="soit-restore-drill",
        actual_database="soit_restore_drill",
        confirmed_database="soit_restore_drill",
        actual_bucket="soit-restore-drill-artifacts",
        confirmed_bucket="soit-restore-drill-artifacts",
    )

    with pytest.raises(compose_restore.RestoreCommandError, match="database"):
        compose_restore._confirm_target(
            actual_project="soit-restore-drill",
            confirmed_project="soit-restore-drill",
            actual_database="soit_restore_drill",
            confirmed_database="soit",
            actual_bucket="soit-restore-drill-artifacts",
            confirmed_bucket="soit-restore-drill-artifacts",
        )
