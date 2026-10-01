"""Evaluation API routes."""

import re

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.v1.agent.dependencies import get_agent_application_service
from app.api.v1.evaluation.dependencies import get_evaluation_service
from app.api.v1.evaluation.handlers import EvaluationHandlers
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.infra.db.pagination import PaginatedResponse
from app.kernel.contracts.context import RequestContext
from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.evaluation.application.schemas import (
    DatasetCaseCreate,
    DatasetCaseResponse,
    DatasetCaseUpdate,
    DatasetCreate,
    DatasetImport,
    DatasetImportResponse,
    DatasetResponse,
    DatasetUpdate,
    DatasetVersionDetailResponse,
    DatasetVersionResponse,
    EvaluationRunCreate,
    ModelReplayCreate,
    ModelReplayResponse,
    ModelReplaySummaryResponse,
    RegressionAnnotationCreate,
    RegressionAnnotationResponse,
    RegressionCaseCreateFromRun,
    RegressionCaseResponse,
    RegressionReportResponse,
    RegressionReportSummaryResponse,
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
    "/run",
    response_model=RegressionReportResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_workspace_write_ctx)],
)
async def run_evaluation(
    payload: EvaluationRunCreate,
    agents: AgentApplicationService = Depends(get_agent_application_service),
    evaluations: RegressionEvaluationService = Depends(get_evaluation_service),
):
    """Run an agent version's regression set now and answer with its report.

    The evaluation the publish gate makes, on demand; every case runs as a
    rehearsal and the report is recorded, so ``regression-reports/latest`` and
    the trend read it afterwards.
    """
    await EvaluationHandlers(evaluations).require_runnable_dataset(
        subject_kind=payload.subject_kind, subject_id=payload.subject_id, dataset=payload.dataset
    )
    result = await agents.run_regressions(
        agent_id=payload.subject_id,
        version_id=payload.subject_version_id,
        dataset=payload.dataset,
        model_ref=payload.model_ref,
        max_cases=payload.max_cases,
    )
    return await EvaluationHandlers(evaluations).get_report(result.report_id)


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


# ----------------------------------------------------------------------
# Datasets
# ----------------------------------------------------------------------


@router.get(
    "/datasets",
    response_model=list[DatasetResponse],
    dependencies=[Depends(require_workspace_read_ctx)],
)
async def list_datasets(
    subject_id: str | None = None,
    status: str | None = Query(default="active", pattern="^(active|archived)?$"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    """The workspace datasets, most recently changed first; an empty ``status`` lists all."""
    return await EvaluationHandlers(service).list_datasets(
        subject_id=subject_id, status=status or None, limit=limit, offset=offset
    )


@router.post(
    "/datasets",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_workspace_write_ctx)],
)
async def create_dataset(
    payload: DatasetCreate,
    agents: AgentApplicationService = Depends(get_agent_application_service),
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    """Create a dataset for an agent; the agent must exist in this workspace."""
    await agents.get_agent(payload.subject_id)
    return await EvaluationHandlers(service).create_dataset(payload)


@router.get(
    "/datasets/{dataset_id}",
    response_model=DatasetResponse,
    dependencies=[Depends(require_workspace_read_ctx)],
)
async def get_dataset(
    dataset_id: str,
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    return await EvaluationHandlers(service).get_dataset(dataset_id)


@router.patch(
    "/datasets/{dataset_id}",
    response_model=DatasetResponse,
    dependencies=[Depends(require_workspace_write_ctx)],
)
async def update_dataset(
    dataset_id: str,
    payload: DatasetUpdate,
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    """Change the description, or archive or restore the dataset through ``status``."""
    return await EvaluationHandlers(service).update_dataset(dataset_id, payload)


@router.delete(
    "/datasets/{dataset_id}",
    response_model=DatasetResponse,
    dependencies=[Depends(require_workspace_write_ctx)],
)
async def archive_dataset(
    dataset_id: str,
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    """Archive the dataset: its cases stop running; nothing is deleted."""
    return await EvaluationHandlers(service).update_dataset(
        dataset_id, DatasetUpdate(status="archived")
    )


@router.get(
    "/datasets/{dataset_id}/cases",
    response_model=PaginatedResponse[DatasetCaseResponse],
    dependencies=[Depends(require_workspace_read_ctx)],
)
async def list_dataset_cases(
    dataset_id: str,
    q: str | None = Query(default=None, max_length=255, description="Part of a case name"),
    page_token: str | None = None,
    page_size: int = 50,
    with_total: bool = False,
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    return await EvaluationHandlers(service).list_dataset_cases(
        dataset_id,
        query=q,
        page_token=page_token,
        page_size=page_size,
        with_total=with_total,
    )


@router.post(
    "/datasets/{dataset_id}/cases",
    response_model=DatasetCaseResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_workspace_write_ctx)],
)
async def add_dataset_case(
    dataset_id: str,
    payload: DatasetCaseCreate,
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    return await EvaluationHandlers(service).add_dataset_case(dataset_id, payload)


@router.get(
    "/datasets/{dataset_id}/cases/{case_id}",
    response_model=DatasetCaseResponse,
    dependencies=[Depends(require_workspace_read_ctx)],
)
async def get_dataset_case(
    dataset_id: str,
    case_id: str,
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    return await EvaluationHandlers(service).get_dataset_case(dataset_id, case_id)


@router.patch(
    "/datasets/{dataset_id}/cases/{case_id}",
    response_model=DatasetCaseResponse,
    dependencies=[Depends(require_workspace_write_ctx)],
)
async def update_dataset_case(
    dataset_id: str,
    case_id: str,
    payload: DatasetCaseUpdate,
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    return await EvaluationHandlers(service).update_dataset_case(dataset_id, case_id, payload)


@router.delete(
    "/datasets/{dataset_id}/cases/{case_id}",
    response_model=DatasetResponse,
    dependencies=[Depends(require_workspace_write_ctx)],
)
async def remove_dataset_case(
    dataset_id: str,
    case_id: str,
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    """Take the case out of the dataset; answers with the dataset at its new revision."""
    return await EvaluationHandlers(service).remove_dataset_case(dataset_id, case_id)


@router.post(
    "/datasets/{dataset_id}/import",
    response_model=DatasetImportResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_workspace_write_ctx)],
)
async def import_dataset(
    dataset_id: str,
    payload: DatasetImport,
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    """Add the cases of a JSONL file, all or none.

    ``content`` is the file text, one case per line. A file with any invalid
    line imports nothing and answers with every offending line.
    """
    return await EvaluationHandlers(service).import_dataset(dataset_id, payload)


@router.get(
    "/datasets/{dataset_id}/export",
    response_class=Response,
    responses={200: {"content": {"application/x-ndjson": {"schema": {"type": "string"}}}}},
    dependencies=[Depends(require_workspace_read_ctx)],
)
async def export_dataset(
    dataset_id: str,
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    """The dataset cases as JSONL, in the format import reads."""
    name, content = await EvaluationHandlers(service).export_dataset(dataset_id)
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "dataset"
    return Response(
        content=content,
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f'attachment; filename="soit-dataset-{slug}.jsonl"',
            "Cache-Control": "no-store",
        },
    )


@router.get(
    "/datasets/{dataset_id}/versions",
    response_model=list[DatasetVersionResponse],
    dependencies=[Depends(require_workspace_read_ctx)],
)
async def list_dataset_versions(
    dataset_id: str,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    """Every revision's size, content hash and what changed, newest first."""
    return await EvaluationHandlers(service).list_dataset_versions(
        dataset_id, limit=limit, offset=offset
    )


@router.get(
    "/datasets/{dataset_id}/versions/{revision}",
    response_model=DatasetVersionDetailResponse,
    dependencies=[Depends(require_workspace_read_ctx)],
)
async def get_dataset_version(
    dataset_id: str,
    revision: int,
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    """One revision with the cases the dataset held at it."""
    return await EvaluationHandlers(service).get_dataset_version(dataset_id, revision)


# ----------------------------------------------------------------------
# Reports
# ----------------------------------------------------------------------


@router.get(
    "/reports",
    response_model=PaginatedResponse[RegressionReportSummaryResponse],
    dependencies=[Depends(require_workspace_read_ctx)],
)
async def list_reports(
    subject_kind: str | None = None,
    subject_id: str | None = None,
    dataset: str | None = None,
    passed: bool | None = None,
    page_token: str | None = None,
    page_size: int = 20,
    with_total: bool = False,
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    """Reports newest first, without their per-case results."""
    return await EvaluationHandlers(service).list_reports(
        subject_kind=subject_kind,
        subject_id=subject_id,
        dataset=dataset,
        passed=passed,
        page_token=page_token,
        page_size=page_size,
        with_total=with_total,
    )


@router.get(
    "/reports/{report_id}",
    response_model=RegressionReportResponse,
    dependencies=[Depends(require_workspace_read_ctx)],
)
async def get_report(
    report_id: str,
    service: RegressionEvaluationService = Depends(get_evaluation_service),
):
    """One report with every case result."""
    return await EvaluationHandlers(service).get_report(report_id)
