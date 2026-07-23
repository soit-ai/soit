"""Contracts for the static N-1 migration fixture."""

from __future__ import annotations

from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = SERVER_ROOT / "tests" / "fixtures" / "n1_release_candidate.sql"


def test_n1_fixture_covers_upgrade_preservation_sentinels() -> None:
    assert FIXTURE_PATH.is_file()
    source = FIXTURE_PATH.read_text(encoding="utf-8")

    for table in (
        "tenants",
        "workspaces",
        "users",
        "tenant_memberships",
        "workspace_memberships",
        "secrets",
        "workflows",
        "workflow_versions",
        "agents",
        "agent_versions",
        "knowledge",
        "knowledge_documents",
        "runs",
        "event_outbox",
    ):
        assert f"INSERT INTO {table}" in source

    assert "secret:sec_n1_release" in source
    assert "n1/minio/release-candidate.txt" in source
    assert "run_n1_release" in source
    assert "evt_n1_release" in source
    assert "CREATE TABLE" not in source.upper()
