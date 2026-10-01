"""Handlers for evaluation APIs."""

from __future__ import annotations

from typing import Any

from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.contracts.context import RequestContext
from app.modules.evaluation.application.dataset_format import snapshot_to_input
from app.modules.evaluation.application.dataset_service import DatasetSummary
from app.modules.evaluation.application.schemas import (
    DatasetCaseCreate,
    DatasetCaseResponse,
    DatasetCaseUpdate,
    DatasetCreate,
    DatasetImport,
    DatasetImportResponse,
    DatasetLatestReport,
    DatasetResponse,
    DatasetUpdate,
    DatasetVersionDetailResponse,
    DatasetVersionResponse,
    RegressionAnnotationCreate,
    RegressionAnnotationResponse,
    RegressionCaseCreateFromRun,
    RegressionCaseResponse,
    RegressionReportResponse,
    RegressionReportSummaryResponse,
    RegressionTrendPoint,
    RegressionTrendResponse,
)
from app.modules.evaluation.application.service import RegressionEvaluationService
from app.modules.evaluation.domain.models import RegressionCase


def dataset_response(summary: DatasetSummary) -> DatasetResponse:
    dataset = summary.dataset
    report = summary.latest_report
    latest = None
    if report is not None:
        counts = report.summary_json or {}
        total = int(counts.get("total") or 0)
        passed_count = int(counts.get("passed") or 0)
        latest = DatasetLatestReport(
            id=report.id,
            passed=report.passed,
            total=total,
            passed_count=passed_count,
            pass_rate=round(passed_count / total, 4) if total else None,
            dataset_revision=report.dataset_revision,
            subject_version_id=report.subject_version_id,
            model_ref=counts.get("model_ref"),
            created_at=report.created_at,
        )
    return DatasetResponse(
        id=dataset.id,
        subject_kind=dataset.subject_kind,
        subject_id=dataset.subject_id,
        name=dataset.name,
        description=dataset.description,
        revision=dataset.revision,
        status=dataset.status,
        case_count=summary.case_count,
        latest_report=latest,
        created_by=dataset.created_by,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
    )


def case_response(case: RegressionCase) -> DatasetCaseResponse:
    base: dict[str, Any] = RegressionCaseResponse.model_validate(case).model_dump()
    return DatasetCaseResponse(**base, input=snapshot_to_input(case.input_snapshot_json))


class EvaluationHandlers:
    def __init__(self, service: RegressionEvaluationService) -> None:
        self.service = service


    async def require_runnable_dataset(
        self, *, subject_kind: str, subject_id: str, dataset: str
    ) -> None:
        """Refuse to run a dataset that was archived, naming the reason.

        An archived dataset has no active cases, so running it would otherwise
        answer only that there is nothing to run.
        """

        row = await self.service.datasets.find_dataset(
            subject_kind=subject_kind, subject_id=subject_id, name=dataset
        )
        if row is not None and row.status == "archived":
            raise ValidationError(
                f"Dataset '{dataset}' is archived; restore it to run it",
                {"dataset": dataset, "reason": "dataset_archived"},
            )

    async def create_case_from_run(
        self,
        ctx: RequestContext,
        payload: RegressionCaseCreateFromRun,
    ) -> RegressionCaseResponse:
        case = await self.service.create_case_from_run(
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
        report = await self.service.get_latest_report(
            subject_kind=subject_kind,
            subject_id=subject_id,
            subject_version_id=subject_version_id,
        )
        if report is None:
            raise NotFoundError("Regression report not found")
        return RegressionReportResponse.model_validate(report)

    async def get_report(self, report_id: str) -> RegressionReportResponse:
        report = await self.service.get_report(report_id)
        return RegressionReportResponse.model_validate(report)

    async def annotate_case(
        self,
        ctx: RequestContext,
        payload: RegressionAnnotationCreate,
    ) -> RegressionAnnotationResponse:
        annotation = await self.service.annotate_case(
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
        annotations = await self.service.list_annotations(
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
        points = await self.service.report_trend(
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

    # ------------------------------------------------------------------
    # Datasets
    # ------------------------------------------------------------------

    async def list_datasets(
        self, *, subject_id: str | None, status: str | None, limit: int, offset: int
    ) -> list[DatasetResponse]:
        summaries = await self.service.datasets.list_datasets(
            subject_id=subject_id, status=status, limit=limit, offset=offset
        )
        return [dataset_response(item) for item in summaries]

    async def create_dataset(self, payload: DatasetCreate) -> DatasetResponse:
        datasets = self.service.datasets
        dataset = await datasets.create_dataset(
            subject_kind=payload.subject_kind,
            subject_id=payload.subject_id,
            name=payload.name,
            description=payload.description,
        )
        return dataset_response(await datasets.summarise(dataset))

    async def get_dataset(self, dataset_id: str) -> DatasetResponse:
        datasets = self.service.datasets
        return dataset_response(await datasets.summarise(await datasets.get_dataset(dataset_id)))

    async def update_dataset(self, dataset_id: str, payload: DatasetUpdate) -> DatasetResponse:
        datasets = self.service.datasets
        dataset = await datasets.update_dataset(
            dataset_id, description=payload.description, status=payload.status
        )
        return dataset_response(await datasets.summarise(dataset))

    async def list_dataset_cases(
        self,
        dataset_id: str,
        *,
        query: str | None,
        page_token: str | None,
        page_size: int,
        with_total: bool,
    ) -> PaginatedResponse[DatasetCaseResponse]:
        datasets = self.service.datasets
        dataset = await datasets.get_dataset(dataset_id)
        limit, token = parse_page_params(page_token, page_size)
        offset = token.offset if token else 0
        cases = await datasets.list_cases(dataset, query=query, limit=limit + 1, offset=offset)
        has_next = len(cases) > limit
        items = [case_response(case) for case in cases[:limit]]
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=offset + len(items) if has_next else None,
            total=await datasets.count_cases(dataset, query=query) if with_total else None,
        )

    async def get_dataset_case(self, dataset_id: str, case_id: str) -> DatasetCaseResponse:
        datasets = self.service.datasets
        dataset = await datasets.get_dataset(dataset_id)
        return case_response(await datasets.get_case(dataset, case_id))

    async def add_dataset_case(
        self, dataset_id: str, payload: DatasetCaseCreate
    ) -> DatasetCaseResponse:
        case = await self.service.datasets.add_case(
            dataset_id, payload.model_dump(exclude={"note"}), note=payload.note
        )
        return case_response(case)

    async def update_dataset_case(
        self, dataset_id: str, case_id: str, payload: DatasetCaseUpdate
    ) -> DatasetCaseResponse:
        case = await self.service.datasets.update_case(
            dataset_id,
            case_id,
            payload.model_dump(exclude={"note"}, exclude_unset=True, exclude_none=True),
            note=payload.note,
        )
        return case_response(case)

    async def remove_dataset_case(self, dataset_id: str, case_id: str) -> DatasetResponse:
        datasets = self.service.datasets
        dataset = await datasets.remove_case(dataset_id, case_id)
        return dataset_response(await datasets.summarise(dataset))

    async def import_dataset(self, dataset_id: str, payload: DatasetImport) -> DatasetImportResponse:
        datasets = self.service.datasets
        dataset, imported = await datasets.import_cases(
            dataset_id, payload.content, note=payload.note
        )
        return DatasetImportResponse(
            imported=imported, dataset=dataset_response(await datasets.summarise(dataset))
        )

    async def export_dataset(self, dataset_id: str) -> tuple[str, str]:
        """The dataset's name and its cases as JSONL text."""
        dataset, content = await self.service.datasets.export_cases(dataset_id)
        return dataset.name, content

    async def list_dataset_versions(
        self, dataset_id: str, *, limit: int, offset: int
    ) -> list[DatasetVersionResponse]:
        datasets = self.service.datasets
        dataset = await datasets.get_dataset(dataset_id)
        versions = await datasets.list_versions(dataset, limit=limit, offset=offset)
        return [DatasetVersionResponse.model_validate(item) for item in versions]

    async def get_dataset_version(
        self, dataset_id: str, revision: int
    ) -> DatasetVersionDetailResponse:
        datasets = self.service.datasets
        dataset = await datasets.get_dataset(dataset_id)
        return DatasetVersionDetailResponse.model_validate(
            await datasets.get_version(dataset, revision)
        )

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    async def list_reports(
        self,
        *,
        subject_kind: str | None,
        subject_id: str | None,
        dataset: str | None,
        passed: bool | None,
        page_token: str | None,
        page_size: int,
        with_total: bool,
    ) -> PaginatedResponse[RegressionReportSummaryResponse]:
        limit, token = parse_page_params(page_token, page_size)
        offset = token.offset if token else 0
        filters: dict[str, Any] = {
            "subject_kind": subject_kind,
            "subject_id": subject_id,
            "dataset": dataset,
            "passed": passed,
        }
        reports = await self.service.list_reports(**filters, limit=limit + 1, offset=offset)
        has_next = len(reports) > limit
        items = [
            RegressionReportSummaryResponse.model_validate(item) for item in reports[:limit]
        ]
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=offset + len(items) if has_next else None,
            total=await self.service.count_reports(**filters) if with_total else None,
        )
