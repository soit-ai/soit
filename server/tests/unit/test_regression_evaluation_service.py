"""Unit tests for Community regression evaluation service."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.evaluation.application.service import (
    RegressionEvaluationResult,
    RegressionEvaluationService,
    RegressionRunResult,
)


def _create_run(
    trace_writer: TraceWriter, *, input_payload: dict[str, Any], output: str
) -> str:
    run = trace_writer.create_run(
        mode="agent",
        subject_kind="agent",
        subject_id="agent_eval",
        subject_version_id="agent_version_1",
        input_summary=json.dumps(input_payload),
    )
    trace_writer.update_run_status(run.id, status="running")
    trace_writer.update_run_status(run.id, status="succeeded", output_summary=output)
    return run.id


def test_create_case_from_historical_run_freezes_input_and_expected_features(
    db, ctx
) -> None:
    run_id = _create_run(
        TraceWriter(db, ctx),
        input_payload={"messages": [{"role": "user", "content": "refund policy"}]},
        output="Refund approval requires account verification.",
    )
    service = RegressionEvaluationService(db=db, ctx=ctx)

    case = service.create_case_from_run(
        run_id=run_id,
        name="refund-policy-answer",
        expected_features={
            "minimum_output_terms": ["refund", "account verification"],
            "max_latency_ms": 1000,
        },
    )

    assert case.source_run_id == run_id
    assert case.subject_kind == "agent"
    assert case.subject_id == "agent_eval"
    assert case.subject_version_id == "agent_version_1"
    assert case.input_snapshot_json == {
        "messages": [{"role": "user", "content": "refund policy"}]
    }
    assert case.expected_features_json["minimum_output_terms"] == [
        "refund",
        "account verification",
    ]


@pytest.mark.asyncio
async def test_evaluate_subject_version_persists_report_with_success_cost_and_latency(
    db, ctx
) -> None:
    trace_writer = TraceWriter(db, ctx)
    run_id = _create_run(
        trace_writer,
        input_payload={
            "messages": [{"role": "user", "content": "create refund review ticket"}]
        },
        output="A review ticket was created using refund policy evidence.",
    )
    service = RegressionEvaluationService(db=db, ctx=ctx)
    service.create_case_from_run(
        run_id=run_id,
        name="refund-ticket-workflow",
        expected_features={
            "minimum_output_terms": ["review ticket", "refund policy"],
            "max_latency_ms": 500,
            "max_cost_amount": 0.25,
        },
    )

    async def runner(_case) -> RegressionRunResult:
        return RegressionRunResult(
            output="A review ticket was created using refund policy evidence.",
            latency_ms=120,
            cost={"amount": 0.05, "tokens": 42},
            run_id="run_replayed",
        )

    result = await service.evaluate_subject_version(
        subject_kind="agent",
        subject_id="agent_eval",
        subject_version_id="agent_version_2",
        runner=runner,
    )
    latest = service.get_latest_report(
        subject_kind="agent",
        subject_id="agent_eval",
        subject_version_id="agent_version_2",
    )

    assert isinstance(result, RegressionEvaluationResult)
    assert result.passed is True
    assert result.summary == {"total": 1, "passed": 1, "failed": 0}
    assert result.metrics["avg_latency_ms"] == 120
    assert result.metrics["total_cost_amount"] == 0.05
    assert latest is not None
    assert latest.id == result.report_id
    assert latest.case_results_json[0]["case_id"]
    assert latest.summary_json == result.summary
