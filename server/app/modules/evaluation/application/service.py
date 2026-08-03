"""Regression evaluation service."""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run
from app.modules.evaluation.application.judge import JudgeError, RegressionJudge
from app.modules.evaluation.domain.models import (
    RegressionAnnotation,
    RegressionCase,
    RegressionReport,
)


@dataclass(frozen=True)
class RegressionRunResult:
    """Observed result from replaying a frozen regression case."""

    output: str
    latency_ms: int
    cost: dict[str, Any]
    run_id: str | None = None


@dataclass(frozen=True)
class RegressionEvaluationResult:
    """Public result returned after persisting a regression report."""

    report_id: str
    passed: bool
    summary: dict[str, int]
    metrics: dict[str, Any]
    cases: list[dict[str, Any]]


RegressionRunner = Callable[
    [RegressionCase], RegressionRunResult | Awaitable[RegressionRunResult]
]


def _unwrap_row(row: Any) -> Any:
    if row is None:
        return None
    if hasattr(row, "_mapping"):
        return row[0]
    if isinstance(row, tuple):
        return row[0]
    return row


class RegressionEvaluationService:
    """Create frozen regression cases and evaluate subject versions."""

    def __init__(
        self,
        *,
        db: Session,
        ctx: RequestContext,
        judge: RegressionJudge | None = None,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.judge = judge

    def create_case_from_run(
        self,
        *,
        run_id: str,
        name: str,
        expected_features: dict[str, Any],
    ) -> RegressionCase:
        run = self._get_run(run_id)
        case = RegressionCase(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            subject_kind=run.subject_kind or run.mode,
            subject_id=run.subject_id or run.id,
            subject_version_id=run.subject_version_id,
            source_run_id=run.id,
            name=name,
            input_snapshot_json=self._parse_input_snapshot(run.input_summary),
            expected_features_json=dict(expected_features),
            created_by=self.ctx.user_id,
        )
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)
        return case

    async def evaluate_subject_version(
        self,
        *,
        subject_kind: str,
        subject_id: str,
        subject_version_id: str,
        runner: RegressionRunner,
        dataset: str = "default",
    ) -> RegressionEvaluationResult:
        cases = self.list_cases(
            subject_kind=subject_kind,
            subject_id=subject_id,
            dataset=dataset,
        )
        revision = self.dataset_revision(cases)
        baseline = self.find_baseline(
            subject_kind=subject_kind,
            subject_id=subject_id,
            dataset=dataset,
            dataset_revision=revision,
        )
        case_results = [await self._evaluate_case(case, runner) for case in cases]
        regressed, fixed = self.compare_to_baseline(case_results, baseline)
        passed_count = sum(1 for item in case_results if item["passed"])
        summary = {
            "total": len(case_results),
            "passed": passed_count,
            "failed": len(case_results) - passed_count,
            "regressed": len(regressed),
            "fixed": len(fixed),
            "baseline_report_id": baseline.id if baseline else None,
            "dataset": dataset,
            "dataset_revision": revision,
        }
        metrics = self._aggregate_metrics(case_results)
        report = RegressionReport(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            subject_kind=subject_kind,
            subject_id=subject_id,
            subject_version_id=subject_version_id,
            dataset=dataset,
            dataset_revision=revision,
            baseline_report_id=baseline.id if baseline else None,
            regressed_case_ids_json=regressed,
            fixed_case_ids_json=fixed,
            passed=summary["failed"] == 0,
            summary_json=summary,
            metrics_json=metrics,
            case_results_json=case_results,
            created_by=self.ctx.user_id,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return RegressionEvaluationResult(
            report_id=report.id,
            passed=report.passed,
            summary=summary,
            metrics=metrics,
            cases=case_results,
        )

    def list_cases(
        self,
        *,
        subject_kind: str,
        subject_id: str,
        dataset: str | None = None,
    ) -> list[RegressionCase]:
        conditions = [
            RegressionCase.tenant_id == self.ctx.tenant_id,
            RegressionCase.workspace_id == self.ctx.workspace_id,
            RegressionCase.subject_kind == subject_kind,
            RegressionCase.subject_id == subject_id,
            RegressionCase.status == "active",
        ]
        if dataset is not None:
            conditions.append(RegressionCase.dataset == dataset)
        rows = self.db.exec(
            select(RegressionCase)
            .where(and_(*conditions))
            .order_by(RegressionCase.created_at)
        ).all()
        return [_unwrap_row(row) for row in rows]

    def dataset_revision(self, cases: list[RegressionCase]) -> int:
        """The revision a report should record for this set of cases.

        Taking the highest revision present means adding a case advances it,
        which is what makes two reports comparable or not.
        """
        return max((int(case.dataset_revision or 1) for case in cases), default=1)

    def find_baseline(
        self,
        *,
        subject_kind: str,
        subject_id: str,
        dataset: str,
        dataset_revision: int,
        exclude_report_id: str | None = None,
    ) -> RegressionReport | None:
        """The most recent comparable report, or None.

        Comparability requires the same dataset at the same revision. A report
        over a different set of cases would make an unrelated difference look
        like a quality change.
        """
        conditions = [
            RegressionReport.tenant_id == self.ctx.tenant_id,
            RegressionReport.workspace_id == self.ctx.workspace_id,
            RegressionReport.subject_kind == subject_kind,
            RegressionReport.subject_id == subject_id,
            RegressionReport.dataset == dataset,
            RegressionReport.dataset_revision == dataset_revision,
        ]
        if exclude_report_id is not None:
            conditions.append(RegressionReport.id != exclude_report_id)
        return _unwrap_row(
            self.db.exec(
                select(RegressionReport)
                .where(and_(*conditions))
                .order_by(desc(RegressionReport.created_at))
            ).first()
        )

    @staticmethod
    def compare_to_baseline(
        case_results: list[dict[str, Any]],
        baseline: RegressionReport | None,
    ) -> tuple[list[str], list[str]]:
        """Split current failures into regressions and long-standing gaps.

        A case that never passed is a known gap; one that used to pass is
        something this change broke. Reporting them together is what makes a
        "regression report" fail to report regressions.
        """
        if baseline is None:
            return [], []
        previous = {
            str(item.get("case_id")): bool(item.get("passed"))
            for item in (baseline.case_results_json or [])
            if item.get("case_id")
        }
        regressed: list[str] = []
        fixed: list[str] = []
        for item in case_results:
            case_id = str(item.get("case_id") or "")
            if case_id not in previous:
                continue
            now_passed = bool(item.get("passed"))
            if previous[case_id] and not now_passed:
                regressed.append(case_id)
            elif not previous[case_id] and now_passed:
                fixed.append(case_id)
        return regressed, fixed

    def get_latest_report(
        self,
        *,
        subject_kind: str,
        subject_id: str,
        subject_version_id: str | None = None,
    ) -> RegressionReport | None:
        conditions = [
            RegressionReport.tenant_id == self.ctx.tenant_id,
            RegressionReport.workspace_id == self.ctx.workspace_id,
            RegressionReport.subject_kind == subject_kind,
            RegressionReport.subject_id == subject_id,
        ]
        if subject_version_id is not None:
            conditions.append(RegressionReport.subject_version_id == subject_version_id)
        return _unwrap_row(
            self.db.exec(
                select(RegressionReport)
                .where(and_(*conditions))
                .order_by(desc(RegressionReport.created_at))
            ).first()
        )

    def annotate_case(
        self,
        *,
        case_id: str,
        verdict: str,
        note: str = "",
        report_id: str | None = None,
    ) -> RegressionAnnotation:
        """Record a human verdict on a case, optionally tied to one report."""
        if verdict not in ("pass", "fail"):
            raise ValidationError("Annotation verdict must be 'pass' or 'fail'")
        case = self._get_case(case_id)
        if report_id is not None:
            self._get_report(report_id)
        annotation = RegressionAnnotation(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            case_id=case.id,
            report_id=report_id,
            verdict=verdict,
            note=note,
            annotated_by=self.ctx.user_id,
        )
        self.db.add(annotation)
        self.db.commit()
        self.db.refresh(annotation)
        return annotation

    def list_annotations(
        self,
        *,
        case_id: str | None = None,
        report_id: str | None = None,
    ) -> list[RegressionAnnotation]:
        if case_id is None and report_id is None:
            raise ValidationError("Provide case_id or report_id to list annotations")
        conditions = [
            RegressionAnnotation.tenant_id == self.ctx.tenant_id,
            RegressionAnnotation.workspace_id == self.ctx.workspace_id,
        ]
        if case_id is not None:
            conditions.append(RegressionAnnotation.case_id == case_id)
        if report_id is not None:
            conditions.append(RegressionAnnotation.report_id == report_id)
        rows = self.db.exec(
            select(RegressionAnnotation)
            .where(and_(*conditions))
            .order_by(RegressionAnnotation.created_at)
        ).all()
        return [_unwrap_row(row) for row in rows]

    def report_trend(
        self,
        *,
        subject_kind: str,
        subject_id: str,
        dataset: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Per-report quality series for a subject, oldest first.

        Points spanning different dataset revisions are still returned —
        hiding them would make a suite change look like missing history — but
        each point carries its revision so a consumer can segment the series.
        """
        conditions = [
            RegressionReport.tenant_id == self.ctx.tenant_id,
            RegressionReport.workspace_id == self.ctx.workspace_id,
            RegressionReport.subject_kind == subject_kind,
            RegressionReport.subject_id == subject_id,
        ]
        if dataset is not None:
            conditions.append(RegressionReport.dataset == dataset)
        rows = self.db.exec(
            select(RegressionReport)
            .where(and_(*conditions))
            .order_by(desc(RegressionReport.created_at))
            .limit(max(1, min(limit, 100)))
        ).all()
        reports = [_unwrap_row(row) for row in rows]
        reports.reverse()
        points: list[dict[str, Any]] = []
        for report in reports:
            summary = report.summary_json or {}
            total = int(summary.get("total") or 0)
            passed_count = int(summary.get("passed") or 0)
            metrics = report.metrics_json or {}
            points.append(
                {
                    "report_id": report.id,
                    "subject_version_id": report.subject_version_id,
                    "dataset": report.dataset,
                    "dataset_revision": report.dataset_revision,
                    "created_at": report.created_at,
                    "passed": report.passed,
                    "total": total,
                    "passed_count": passed_count,
                    "pass_rate": round(passed_count / total, 4) if total else None,
                    "regressed": len(report.regressed_case_ids_json or []),
                    "fixed": len(report.fixed_case_ids_json or []),
                    "avg_latency_ms": metrics.get("avg_latency_ms"),
                    "total_cost_amount": metrics.get("total_cost_amount"),
                }
            )
        return points

    def _get_case(self, case_id: str) -> RegressionCase:
        case = _unwrap_row(
            self.db.exec(
                select(RegressionCase).where(
                    and_(
                        RegressionCase.id == case_id,
                        RegressionCase.tenant_id == self.ctx.tenant_id,
                        RegressionCase.workspace_id == self.ctx.workspace_id,
                    )
                )
            ).first()
        )
        if case is None:
            raise NotFoundError(f"Regression case not found: {case_id}")
        return case

    def _get_report(self, report_id: str) -> RegressionReport:
        report = _unwrap_row(
            self.db.exec(
                select(RegressionReport).where(
                    and_(
                        RegressionReport.id == report_id,
                        RegressionReport.tenant_id == self.ctx.tenant_id,
                        RegressionReport.workspace_id == self.ctx.workspace_id,
                    )
                )
            ).first()
        )
        if report is None:
            raise NotFoundError(f"Regression report not found: {report_id}")
        return report

    async def _evaluate_case(
        self, case: RegressionCase, runner: RegressionRunner
    ) -> dict[str, Any]:
        maybe_result = runner(case)
        result = (
            await maybe_result if inspect.isawaitable(maybe_result) else maybe_result
        )
        failures = self._failure_reasons(case, result)
        item: dict[str, Any] = {
            "case_id": case.id,
            "name": case.name,
            "run_id": result.run_id,
            "latency_ms": result.latency_ms,
            "cost": result.cost,
        }
        criteria = (case.expected_features_json or {}).get("llm_judge")
        if criteria is not None:
            verdict_payload, judge_failures = await self._judge_case(
                case, result, criteria
            )
            if verdict_payload is not None:
                item["judge"] = verdict_payload
            failures.extend(judge_failures)
        item["passed"] = not failures
        item["failure_reasons"] = failures
        return item

    async def _judge_case(
        self,
        case: RegressionCase,
        result: RegressionRunResult,
        criteria: Any,
    ) -> tuple[dict[str, Any] | None, list[str]]:
        """Score one output against the case's rubric, failing closed.

        A case that asks for judgment must never pass because the judge was
        missing or broken; that would report quality that was never measured.
        """
        if not isinstance(criteria, dict) or not str(criteria.get("rubric") or "").strip():
            return None, ["llm_judge_criteria_invalid"]
        if self.judge is None:
            return None, ["llm_judge_unconfigured"]
        min_score = float(criteria.get("min_score", 0.7))
        try:
            verdict = await self.judge.score(
                rubric=str(criteria["rubric"]),
                case_input=case.input_snapshot_json or {},
                output=result.output,
                model=criteria.get("model"),
            )
        except JudgeError as exc:
            return {"error": str(exc), "min_score": min_score}, [
                f"llm_judge_error: {exc}"
            ]
        payload = {
            "score": verdict.score,
            "reasoning": verdict.reasoning,
            "model": verdict.model,
            "min_score": min_score,
        }
        if verdict.score < min_score:
            return payload, ["llm_judge_below_threshold"]
        return payload, []

    def _get_run(self, run_id: str) -> Run:
        run = _unwrap_row(
            self.db.exec(
                select(Run).where(
                    and_(
                        Run.id == run_id,
                        Run.tenant_id == self.ctx.tenant_id,
                        Run.workspace_id == self.ctx.workspace_id,
                    )
                )
            ).first()
        )
        if run is None:
            raise NotFoundError(f"Run not found: {run_id}")
        return run

    @staticmethod
    def _parse_input_snapshot(input_summary: str | None) -> dict[str, Any]:
        if not input_summary:
            return {}
        try:
            payload = json.loads(input_summary)
        except json.JSONDecodeError:
            return {"input_summary": input_summary}
        return payload if isinstance(payload, dict) else {"input": payload}

    @staticmethod
    def _failure_reasons(
        case: RegressionCase, result: RegressionRunResult
    ) -> list[str]:
        expected = case.expected_features_json or {}
        output_lc = result.output.lower()
        failures = [
            f"output missing term: {term}"
            for term in expected.get("minimum_output_terms", [])
            if str(term).lower() not in output_lc
        ]
        max_latency_ms = expected.get("max_latency_ms")
        if max_latency_ms is not None and result.latency_ms > int(max_latency_ms):
            failures.append("latency_above_threshold")
        max_cost_amount = expected.get("max_cost_amount")
        cost_amount = float((result.cost or {}).get("amount") or 0)
        if max_cost_amount is not None and cost_amount > float(max_cost_amount):
            failures.append("cost_above_threshold")
        return failures

    @staticmethod
    def _aggregate_metrics(case_results: list[dict[str, Any]]) -> dict[str, Any]:
        if not case_results:
            return {"avg_latency_ms": 0, "total_cost_amount": 0.0}
        total_latency = sum(int(item["latency_ms"]) for item in case_results)
        total_cost = sum(
            float((item.get("cost") or {}).get("amount") or 0) for item in case_results
        )
        return {
            "avg_latency_ms": int(total_latency / len(case_results)),
            "total_cost_amount": round(total_cost, 8),
        }
