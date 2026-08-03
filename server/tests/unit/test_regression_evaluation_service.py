"""Unit tests for Community regression evaluation service."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.evaluation.application.judge import JudgeError, JudgeVerdict
from app.modules.evaluation.application.service import (
    RegressionEvaluationResult,
    RegressionEvaluationService,
    RegressionRunResult,
)


class _StubJudge:
    """Judge with a scripted verdict (or failure) per call."""

    def __init__(self, *, score: float = 1.0, error: Exception | None = None):
        self.score_value = score
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def score(self, *, rubric, case_input, output, model=None) -> JudgeVerdict:
        self.calls.append(
            {"rubric": rubric, "input": case_input, "output": output, "model": model}
        )
        if self.error is not None:
            raise self.error
        return JudgeVerdict(score=self.score_value, reasoning="scripted", model=model)


def _passing_runner(output: str = "ok"):
    async def runner(_case) -> RegressionRunResult:
        return RegressionRunResult(
            output=output, latency_ms=10, cost={"amount": 0.01}, run_id="run_replay"
        )

    return runner


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
    assert result.summary == {
        "total": 1,
        "passed": 1,
        "failed": 0,
        # A first report has nothing to compare against, so nothing can be
        # called a regression.
        "regressed": 0,
        "fixed": 0,
        "baseline_report_id": None,
        "dataset": "default",
        "dataset_revision": 1,
    }
    assert result.metrics["avg_latency_ms"] == 120
    assert result.metrics["total_cost_amount"] == 0.05
    assert latest is not None
    assert latest.id == result.report_id
    assert latest.case_results_json[0]["case_id"]
    assert latest.summary_json == result.summary


def _judge_case(service: RegressionEvaluationService, trace_writer, *, min_score=0.7):
    run_id = _create_run(
        trace_writer,
        input_payload={"messages": [{"role": "user", "content": "summarize policy"}]},
        output="The policy covers refunds.",
    )
    return service.create_case_from_run(
        run_id=run_id,
        name="judged-summary",
        expected_features={
            "llm_judge": {
                "rubric": "Output must accurately summarize the refund policy.",
                "min_score": min_score,
            }
        },
    )


@pytest.mark.asyncio
async def test_llm_judge_gates_cases_on_min_score(db, ctx) -> None:
    trace_writer = TraceWriter(db, ctx)
    judge = _StubJudge(score=0.4)
    service = RegressionEvaluationService(db=db, ctx=ctx, judge=judge)
    _judge_case(service, trace_writer, min_score=0.7)

    failing = await service.evaluate_subject_version(
        subject_kind="agent",
        subject_id="agent_eval",
        subject_version_id="v_low",
        runner=_passing_runner(),
    )

    assert failing.passed is False
    case_result = failing.cases[0]
    assert case_result["failure_reasons"] == ["llm_judge_below_threshold"]
    assert case_result["judge"]["score"] == 0.4
    assert case_result["judge"]["min_score"] == 0.7
    assert judge.calls[0]["rubric"].startswith("Output must accurately")

    judge.score_value = 0.9
    passing = await service.evaluate_subject_version(
        subject_kind="agent",
        subject_id="agent_eval",
        subject_version_id="v_high",
        runner=_passing_runner(),
    )
    assert passing.passed is True
    assert passing.cases[0]["judge"]["score"] == 0.9


@pytest.mark.asyncio
async def test_llm_judge_fails_closed_when_unconfigured(db, ctx) -> None:
    trace_writer = TraceWriter(db, ctx)
    service = RegressionEvaluationService(db=db, ctx=ctx)
    _judge_case(service, trace_writer)

    result = await service.evaluate_subject_version(
        subject_kind="agent",
        subject_id="agent_eval",
        subject_version_id="v_nojudge",
        runner=_passing_runner(),
    )

    assert result.passed is False
    assert result.cases[0]["failure_reasons"] == ["llm_judge_unconfigured"]


@pytest.mark.asyncio
async def test_llm_judge_errors_fail_the_case_not_the_report(db, ctx) -> None:
    trace_writer = TraceWriter(db, ctx)
    judge = _StubJudge(error=JudgeError("judge model call failed: boom"))
    service = RegressionEvaluationService(db=db, ctx=ctx, judge=judge)
    _judge_case(service, trace_writer)

    result = await service.evaluate_subject_version(
        subject_kind="agent",
        subject_id="agent_eval",
        subject_version_id="v_err",
        runner=_passing_runner(),
    )

    assert result.passed is False
    reasons = result.cases[0]["failure_reasons"]
    assert len(reasons) == 1
    assert reasons[0].startswith("llm_judge_error:")
    assert result.cases[0]["judge"]["error"].startswith("judge model call failed")


@pytest.mark.asyncio
async def test_invalid_judge_criteria_fail_the_case(db, ctx) -> None:
    trace_writer = TraceWriter(db, ctx)
    service = RegressionEvaluationService(db=db, ctx=ctx, judge=_StubJudge())
    run_id = _create_run(
        trace_writer, input_payload={"q": "x"}, output="anything"
    )
    service.create_case_from_run(
        run_id=run_id,
        name="empty-rubric",
        expected_features={"llm_judge": {"rubric": "  "}},
    )

    result = await service.evaluate_subject_version(
        subject_kind="agent",
        subject_id="agent_eval",
        subject_version_id="v_bad_criteria",
        runner=_passing_runner(),
    )

    assert result.cases[0]["failure_reasons"] == ["llm_judge_criteria_invalid"]


@pytest.mark.asyncio
async def test_annotations_record_human_verdicts_scoped_to_case_and_report(
    db, ctx
) -> None:
    trace_writer = TraceWriter(db, ctx)
    service = RegressionEvaluationService(db=db, ctx=ctx)
    run_id = _create_run(trace_writer, input_payload={"q": "x"}, output="answer")
    case = service.create_case_from_run(
        run_id=run_id, name="annotated", expected_features={}
    )
    report = await service.evaluate_subject_version(
        subject_kind="agent",
        subject_id="agent_eval",
        subject_version_id="v_ann",
        runner=_passing_runner(),
    )

    annotation = service.annotate_case(
        case_id=case.id,
        verdict="fail",
        note="Output is fluent but factually wrong.",
        report_id=report.report_id,
    )

    assert annotation.verdict == "fail"
    assert annotation.annotated_by == ctx.user_id
    by_case = service.list_annotations(case_id=case.id)
    by_report = service.list_annotations(report_id=report.report_id)
    assert [item.id for item in by_case] == [annotation.id]
    assert [item.id for item in by_report] == [annotation.id]

    with pytest.raises(ValidationError):
        service.annotate_case(case_id=case.id, verdict="maybe")
    with pytest.raises(NotFoundError):
        service.annotate_case(case_id="regcase_missing", verdict="pass")
    with pytest.raises(NotFoundError):
        service.annotate_case(
            case_id=case.id, verdict="pass", report_id="regrep_missing"
        )
    with pytest.raises(ValidationError):
        service.list_annotations()


@pytest.mark.asyncio
async def test_report_trend_returns_versions_oldest_first_with_pass_rates(
    db, ctx
) -> None:
    trace_writer = TraceWriter(db, ctx)
    service = RegressionEvaluationService(db=db, ctx=ctx)
    run_id = _create_run(
        trace_writer,
        input_payload={"q": "refund"},
        output="Refund policy answer.",
    )
    service.create_case_from_run(
        run_id=run_id,
        name="trend-case",
        expected_features={"minimum_output_terms": ["refund"]},
    )

    await service.evaluate_subject_version(
        subject_kind="agent",
        subject_id="agent_eval",
        subject_version_id="v1",
        runner=_passing_runner("Refund granted."),
    )
    await service.evaluate_subject_version(
        subject_kind="agent",
        subject_id="agent_eval",
        subject_version_id="v2",
        runner=_passing_runner("No matching terms here."),
    )

    points = service.report_trend(subject_kind="agent", subject_id="agent_eval")

    assert [point["subject_version_id"] for point in points] == ["v1", "v2"]
    assert points[0]["passed"] is True
    assert points[0]["pass_rate"] == 1.0
    assert points[1]["passed"] is False
    assert points[1]["pass_rate"] == 0.0
    assert points[1]["regressed"] == 1
    assert all(point["dataset"] == "default" for point in points)


@pytest.mark.asyncio
async def test_three_scenario_datasets_evaluate_independently(db, ctx) -> None:
    """Regression suites for distinct scenarios must not bleed into each other."""
    trace_writer = TraceWriter(db, ctx)
    service = RegressionEvaluationService(db=db, ctx=ctx, judge=_StubJudge(score=0.95))
    scenarios = {
        "support-ticket": {
            "input": {"messages": [{"role": "user", "content": "open refund ticket"}]},
            "expected": {"minimum_output_terms": ["ticket"]},
            "output": "A support ticket was opened.",
        },
        "knowledge-qa": {
            "input": {"messages": [{"role": "user", "content": "what is the policy"}]},
            "expected": {
                "llm_judge": {"rubric": "Answer must ground in policy.", "min_score": 0.8}
            },
            "output": "The policy requires verification.",
        },
        "workflow-summary": {
            "input": {"messages": [{"role": "user", "content": "summarize run"}]},
            "expected": {"minimum_output_terms": ["summary"], "max_latency_ms": 5000},
            "output": "Here is the run summary.",
        },
    }
    for dataset, scenario in scenarios.items():
        run_id = _create_run(
            trace_writer, input_payload=scenario["input"], output=scenario["output"]
        )
        case = service.create_case_from_run(
            run_id=run_id, name=f"{dataset}-case", expected_features=scenario["expected"]
        )
        case.dataset = dataset
        db.add(case)
        db.commit()

    results = {}
    for dataset, scenario in scenarios.items():
        results[dataset] = await service.evaluate_subject_version(
            subject_kind="agent",
            subject_id="agent_eval",
            subject_version_id="v_scenarios",
            runner=_passing_runner(scenario["output"]),
            dataset=dataset,
        )

    for dataset, result in results.items():
        assert result.passed is True, dataset
        assert result.summary["total"] == 1, dataset
        assert result.summary["dataset"] == dataset
    trends = {
        dataset: service.report_trend(
            subject_kind="agent", subject_id="agent_eval", dataset=dataset
        )
        for dataset in scenarios
    }
    assert all(len(points) == 1 for points in trends.values())
