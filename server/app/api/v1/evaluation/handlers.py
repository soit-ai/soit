"""Handlers for evaluation APIs."""

from __future__ import annotations

from app.kernel.commons.errors import NotFoundError
from app.kernel.contracts.context import RequestContext
from app.modules.evaluation.application.schemas import (
    RegressionCaseCreateFromRun,
    RegressionCaseResponse,
    RegressionReportResponse,
)
from app.modules.evaluation.application.service import RegressionEvaluationService


class EvaluationHandlers:
    def __init__(self, service: RegressionEvaluationService) -> None:
        self.service = service

    async def create_case_from_run(
        self,
        ctx: RequestContext,
        payload: RegressionCaseCreateFromRun,
    ) -> RegressionCaseResponse:
        case = self.service.create_case_from_run(
            run_id=payload.run_id,
            name=payload.name,
            expected_features=payload.expected_features,
        )
        return RegressionCaseResponse.model_validate(case)

    async def get_latest_report(
        self,
        ctx: RequestContext,
        *,
        subject_kind: str,
        subject_id: str,
        subject_version_id: str | None,
    ) -> RegressionReportResponse:
        report = self.service.get_latest_report(
            subject_kind=subject_kind,
            subject_id=subject_id,
            subject_version_id=subject_version_id,
        )
        if report is None:
            raise NotFoundError("Regression report not found")
        return RegressionReportResponse.model_validate(report)
