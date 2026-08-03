"""Handlers for evaluation APIs."""

from __future__ import annotations

from app.kernel.commons.errors import NotFoundError
from app.kernel.contracts.context import RequestContext
from app.modules.evaluation.application.schemas import (
    RegressionAnnotationCreate,
    RegressionAnnotationResponse,
    RegressionCaseCreateFromRun,
    RegressionCaseResponse,
    RegressionReportResponse,
    RegressionTrendPoint,
    RegressionTrendResponse,
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

    async def annotate_case(
        self,
        ctx: RequestContext,
        payload: RegressionAnnotationCreate,
    ) -> RegressionAnnotationResponse:
        annotation = self.service.annotate_case(
            case_id=payload.case_id,
            verdict=payload.verdict,
            note=payload.note,
            report_id=payload.report_id,
        )
        return RegressionAnnotationResponse.model_validate(annotation)

    async def list_annotations(
        self,
        ctx: RequestContext,
        *,
        case_id: str | None,
        report_id: str | None,
    ) -> list[RegressionAnnotationResponse]:
        annotations = self.service.list_annotations(
            case_id=case_id, report_id=report_id
        )
        return [
            RegressionAnnotationResponse.model_validate(item) for item in annotations
        ]

    async def get_report_trend(
        self,
        ctx: RequestContext,
        *,
        subject_kind: str,
        subject_id: str,
        dataset: str | None,
        limit: int,
    ) -> RegressionTrendResponse:
        points = self.service.report_trend(
            subject_kind=subject_kind,
            subject_id=subject_id,
            dataset=dataset,
            limit=limit,
        )
        return RegressionTrendResponse(
            subject_kind=subject_kind,
            subject_id=subject_id,
            dataset=dataset,
            points=[RegressionTrendPoint.model_validate(point) for point in points],
        )
