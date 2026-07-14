"""Governance demo verifier integration tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.modelhub.domain.models import Provider, ProviderModel  # noqa: F401


def _args(**overrides):
    data = {
        "email": "governance-demo@example.com",
        "password": "changeme123",
        "name": "Governance Demo User",
        "tenant_name": "governance-demo-tenant",
        "workspace_name": "default",
        "cases_path": Path("tests/fixtures/support_ticket_golden_set.json"),
        "json_output": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.mark.asyncio
async def test_governance_demo_verifier_builds_20_minute_evidence_chain(db):
    from scripts.verify_governance_demo import verify_governance_demo

    report = await verify_governance_demo(db, _args())

    assert report["scenario"] == "governance_demo_20_min"
    assert report["passed"] is True
    assert report["summary"]["demo_minutes"] <= 20

    evidence = report["evidence"]
    assert evidence["permissions"]["passed"] is True
    assert evidence["permissions"]["workspace_role"] == "Owner"
    assert evidence["permissions"]["agent_binding_chains"] >= 1

    assert evidence["secrets"]["passed"] is True
    assert evidence["secrets"]["secret_count"] >= 2

    assert evidence["call_audit"]["passed"] is True
    assert evidence["call_audit"]["audit_count"] >= 1

    assert evidence["cost_attribution"]["passed"] is True
    assert evidence["cost_attribution"]["cost_entries"] >= 1

    assert evidence["replay"]["passed"] is True
    assert evidence["replay"]["run_explorer_url"].startswith("/observe/runs/")
    assert evidence["replay"]["step_count"] >= 1
    assert evidence["replay"]["citation_count"] >= 1

    assert evidence["regression"]["passed"] is True
    assert evidence["regression"]["summary"] == {"total": 2, "passed": 2, "failed": 0}

    assert [step["section"] for step in report["demo_steps"]] == [
        "permissions",
        "secrets",
        "call_audit",
        "cost_attribution",
        "replay",
        "regression",
    ]
