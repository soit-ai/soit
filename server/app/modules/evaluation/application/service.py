"""Regression evaluation service."""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run
from app.modules.evaluation.domain.models import RegressionCase, RegressionReport


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

    def __init__(self, *, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

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
    ) -> RegressionEvaluationResult:
        cases = self.list_cases(subject_kind=subject_kind, subject_id=subject_id)
        case_results = [await self._evaluate_case(case, runner) for case in cases]
        passed_count = sum(1 for item in case_results if item["passed"])
        summary = {
            "total": len(case_results),
            "passed": passed_count,
            "failed": len(case_results) - passed_count,
        }
        metrics = self._aggregate_metrics(case_results)
        report = RegressionReport(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            subject_kind=subject_kind,
            subject_id=subject_id,
            subject_version_id=subject_version_id,
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

    def list_cases(self, *, subject_kind: str, subject_id: str) -> list[RegressionCase]:
        rows = self.db.exec(
            select(RegressionCase)
            .where(
                and_(
                    RegressionCase.tenant_id == self.ctx.tenant_id,
                    RegressionCase.workspace_id == self.ctx.workspace_id,
                    RegressionCase.subject_kind == subject_kind,
                    RegressionCase.subject_id == subject_id,
                    RegressionCase.status == "active",
                )
            )
            .order_by(RegressionCase.created_at)
        ).all()
        return [_unwrap_row(row) for row in rows]

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

    async def _evaluate_case(
        self, case: RegressionCase, runner: RegressionRunner
    ) -> dict[str, Any]:
        maybe_result = runner(case)
        result = (
            await maybe_result if inspect.isawaitable(maybe_result) else maybe_result
        )
        failures = self._failure_reasons(case, result)
        return {
            "case_id": case.id,
            "name": case.name,
            "passed": not failures,
            "failure_reasons": failures,
            "run_id": result.run_id,
            "latency_ms": result.latency_ms,
            "cost": result.cost,
        }

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
