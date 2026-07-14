"""Support/ticket regression evaluator integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.modelhub.domain.models import Provider, ProviderModel  # noqa: F401
from scripts.evaluate_support_ticket_regression import (
    evaluate_support_ticket_regression,
)


def _args(**overrides):
    data = {
        "email": "support-eval@example.com",
        "password": "changeme123",
        "name": "Support Eval User",
        "tenant_name": "support-eval-tenant",
        "workspace_name": "default",
        "cases_path": Path("tests/fixtures/support_ticket_golden_set.json"),
        "json_output": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.mark.asyncio
async def test_support_ticket_regression_evaluator_generates_machine_readable_evidence(db):
    report = await evaluate_support_ticket_regression(db, _args())

    assert report["scenario"] == "support_ticket"
    assert report["passed"] is True, json.dumps(report["cases"], indent=2, sort_keys=True)
    assert report["summary"] == {"total": 2, "passed": 2, "failed": 0}
    assert {case["case_id"] for case in report["cases"]} == {
        "refund_policy_answer",
        "refund_ticket_workflow",
    }

    policy_case = next(case for case in report["cases"] if case["case_id"] == "refund_policy_answer")
    assert policy_case["passed"] is True
    assert policy_case["governance_passed"] is True
    assert policy_case["governance_failures"] == []
    policy_evidence = {item["key"]: item for item in policy_case["governance_evidence"]}
    for key in ("actor_scope", "subject_version", "trace_timeline", "knowledge_citation", "cost_attribution", "replay_ready"):
        assert policy_evidence[key]["status"] == "pass"
    assert policy_case["tool_call_count"] == 0
    assert policy_case["citation_count"] >= 1
    assert policy_case["expected_citation_source"] == "refund-policy.md"
    assert policy_case["run_id"]
    assert policy_case["response_id"]
    assert policy_case["latency_ms"] >= 0
    assert "refund" in policy_case["output"].lower()

    workflow_case = next(case for case in report["cases"] if case["case_id"] == "refund_ticket_workflow")
    assert workflow_case["passed"] is True
    assert workflow_case["governance_passed"] is True
    assert workflow_case["governance_failures"] == []
    workflow_evidence = {item["key"]: item for item in workflow_case["governance_evidence"]}
    for key in (
        "actor_scope",
        "subject_version",
        "trace_timeline",
        "knowledge_citation",
        "cost_attribution",
        "replay_ready",
        "tool_call",
        "child_workflow",
        "audit_record",
        "secret_boundary",
        "egress_policy",
    ):
        assert workflow_evidence[key]["status"] == "pass"
    assert workflow_case["tool_call_count"] >= 1
    assert workflow_case["citation_count"] >= 1
    assert workflow_case["audit_count"] >= 1
    assert workflow_case["child_run_count"] >= 1
    assert workflow_case["cost"]["entries"] >= 1
    assert workflow_case["run_explorer_url"].startswith("/observe/runs/")
    assert workflow_case["failure_reasons"] == []
