"""Evaluation API routes."""

from fastapi import APIRouter, Depends, status

from app.api.v1.agent.dependencies import get_agent_application_service
from app.api.v1.evaluation.dependencies import get_evaluation_service
from app.api.v1.evaluation.handlers import EvaluationHandlers
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.kernel.contracts.context import RequestContext
from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.evaluation.application.schemas import (
    ModelReplayCreate,
    ModelReplayResponse,
    ModelReplaySummaryResponse,
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


@router.post(
    "/model-replays",
    response_model=ModelReplayResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_workspace_write_ctx)],
)
async def create_model_replay(
    payload: ModelReplayCreate,
    agents: AgentApplicationService = Depends(get_agent_application_service),
):
    """Replay agents' regression sets on a candidate model next to their own.

    Runs every case twice, as rehearsals, and answers when all have run.
    """
    replay = await agents.replay_regressions_on_model(
        model_ref=payload.model_ref,
        agent_ids=payload.agent_ids,
        dataset=payload.dataset,
        max_cases=payload.max_cases,
    )
    return ModelReplayResponse.model_validate(replay)


@router.get(
    "/model-replays",
    response_model=list[ModelReplaySummaryResponse],
    dependencies=[Depends(require_workspace_read_ctx)],
)
async def list_model_replays(
    limit: int = 20,
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    return [
        ModelReplaySummaryResponse.model_validate(replay)
        for replay in await service.list_model_replays(limit=limit)
    ]


@router.get(
    "/model-replays/{replay_id}",
    response_model=ModelReplayResponse,
    dependencies=[Depends(require_workspace_read_ctx)],
)
async def get_model_replay(
    replay_id: str,
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    return ModelReplayResponse.model_validate(await service.get_model_replay(replay_id))
