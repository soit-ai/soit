"""Evaluation API routes."""

from fastapi import APIRouter, Depends, status

from app.api.v1.evaluation.dependencies import get_evaluation_service
from app.api.v1.evaluation.handlers import EvaluationHandlers
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.kernel.contracts.context import RequestContext
from app.modules.evaluation.application.schemas import (
    RegressionAnnotationCreate,
    RegressionAnnotationResponse,
    RegressionCaseCreateFromRun,
    RegressionCaseResponse,
    RegressionReportResponse,
    RegressionTrendResponse,
)
from app.modules.evaluation.application.service import RegressionEvaluationService

router = APIRouter()


@router.post(
    "/regression-cases/from-run",
    response_model=RegressionCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_regression_case_from_run(
    payload: RegressionCaseCreateFromRun,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    return await EvaluationHandlers(service).create_case_from_run(ctx, payload)


@router.post(
    "/regression-annotations",
    response_model=RegressionAnnotationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_regression_annotation(
    payload: RegressionAnnotationCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    return await EvaluationHandlers(service).annotate_case(ctx, payload)


@router.get(
    "/regression-annotations",
    response_model=list[RegressionAnnotationResponse],
)
async def list_regression_annotations(
    case_id: str | None = None,
    report_id: str | None = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    return await EvaluationHandlers(service).list_annotations(
        ctx, case_id=case_id, report_id=report_id
    )


@router.get("/regression-reports/trend", response_model=RegressionTrendResponse)
async def get_regression_report_trend(
    subject_kind: str,
    subject_id: str,
    dataset: str | None = None,
    limit: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    return await EvaluationHandlers(service).get_report_trend(
        ctx,
        subject_kind=subject_kind,
        subject_id=subject_id,
        dataset=dataset,
        limit=limit,
    )


@router.get("/regression-reports/latest", response_model=RegressionReportResponse)
async def get_latest_regression_report(
    subject_kind: str,
    subject_id: str,
    subject_version_id: str | None = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    return await EvaluationHandlers(service).get_latest_report(
        ctx,
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_version_id=subject_version_id,
    )
