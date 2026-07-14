"""Evaluation API entrypoint tests."""

from __future__ import annotations

import json

from fastapi import status

from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.evaluation.application.service import (
    RegressionEvaluationService,
    RegressionRunResult,
)


def _headers() -> dict[str, str]:
    return {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}


def test_regression_case_api_freezes_historical_run_and_exposes_latest_report(
    client, db, ctx
) -> None:
    run = TraceWriter(db, ctx).create_run(
        mode="agent",
        subject_kind="agent",
        subject_id="agent_eval_api",
        subject_version_id="agent_version_1",
        input_summary=json.dumps(
            {"messages": [{"role": "user", "content": "refund policy"}]}
        ),
    )
    service = RegressionEvaluationService(db=db, ctx=ctx)

    response = client.post(
        "/api/v1/evaluations/regression-cases/from-run",
        json={
            "run_id": run.id,
            "name": "refund-policy-answer",
            "expected_features": {
                "minimum_output_terms": ["refund policy"],
                "max_latency_ms": 500,
                "max_cost_amount": 0.25,
            },
        },
        headers=_headers(),
    )

    assert response.status_code == status.HTTP_201_CREATED
    case = response.json()["data"]
    assert case["source_run_id"] == run.id
    assert case["subject_kind"] == "agent"
    assert case["subject_id"] == "agent_eval_api"
    assert case["input_snapshot_json"]["messages"][0]["content"] == "refund policy"

    async def runner(_case) -> RegressionRunResult:
        return RegressionRunResult(
            output="refund policy evidence",
            latency_ms=120,
            cost={"amount": 0.05},
            run_id="run_replayed_api",
        )

    report = client.portal.call(
        lambda: service.evaluate_subject_version(
            subject_kind="agent",
            subject_id="agent_eval_api",
            subject_version_id="agent_version_2",
            runner=runner,
        )
    )
    latest_response = client.get(
        "/api/v1/evaluations/regression-reports/latest",
        params={
            "subject_kind": "agent",
            "subject_id": "agent_eval_api",
            "subject_version_id": "agent_version_2",
        },
        headers=_headers(),
    )

    assert latest_response.status_code == status.HTTP_200_OK
    latest = latest_response.json()["data"]
    assert latest["id"] == report.report_id
    assert latest["summary_json"] == {"total": 1, "passed": 1, "failed": 0}
    assert latest["metrics_json"]["avg_latency_ms"] == 120
