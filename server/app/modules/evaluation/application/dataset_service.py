"""Evaluation datasets: named, versioned sets of regression cases.

Cases stay in ``regression_cases`` and name their set in ``dataset``; this
service owns what makes a set an object of its own. Every change made through
it advances the dataset's revision, stamps the cases it touched with that
revision, writes a snapshot of the whole set, and leaves an audit event, all in
the one commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import and_, desc, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import ConflictError, NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.audit import AuditEvent
from app.modules.evaluation.application import dataset_format
from app.modules.evaluation.application.dataset_format import DatasetCaseDocument
from app.modules.evaluation.domain.models import (
    RegressionCase,
    RegressionDataset,
    RegressionDatasetVersion,
    RegressionReport,
)

DEFAULT_DATASET = "default"
MAX_NAME_LENGTH = 255
MAX_DESCRIPTION_LENGTH = 2000
MAX_NOTE_LENGTH = 500
MAX_ACTIVE_CASES = 5000
"""A set this large is slow to run and to snapshot; refuse growth past it."""


def _unwrap(row: Any) -> Any:
    if row is None:
        return None
    if hasattr(row, "_mapping") or isinstance(row, tuple):
        return row[0]
    return row


@dataclass(frozen=True)
class DatasetSummary:
    """A dataset with the figures a list shows next to it."""

    dataset: RegressionDataset
    case_count: int
    latest_report: RegressionReport | None


class RegressionDatasetService:
    """Create, edit, import, export and version evaluation datasets."""

    def __init__(self, *, db: AsyncSession, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    # ------------------------------------------------------------------
    # Datasets
    # ------------------------------------------------------------------

    async def list_datasets(
        self,
        *,
        subject_id: str | None = None,
        status: str | None = "active",
        limit: int = 100,
        offset: int = 0,
    ) -> list[DatasetSummary]:
        conditions = self._dataset_scope()
        if subject_id is not None:
            conditions.append(RegressionDataset.subject_id == subject_id)
        if status is not None:
            conditions.append(RegressionDataset.status == status)
        rows = (
            await self.db.exec(
                select(RegressionDataset)
                .where(and_(*conditions))
                .order_by(desc(RegressionDataset.updated_at), RegressionDataset.id)
                .limit(max(1, min(limit, 200)))
                .offset(max(0, offset))
            )
        ).all()
        datasets = [_unwrap(row) for row in rows]
        return [await self._summarise(dataset) for dataset in datasets]

    async def summarise(self, dataset: RegressionDataset) -> DatasetSummary:
        return await self._summarise(dataset)

    async def get_dataset(self, dataset_id: str) -> RegressionDataset:
        dataset = _unwrap(
            (
                await self.db.exec(
                    select(RegressionDataset).where(
                        and_(RegressionDataset.id == dataset_id, *self._dataset_scope())
                    )
                )
            ).first()
        )
        if dataset is None:
            raise NotFoundError(f"Dataset not found: {dataset_id}")
        return dataset

    async def find_dataset(
        self, *, subject_kind: str, subject_id: str, name: str
    ) -> RegressionDataset | None:
        return _unwrap(
            (
                await self.db.exec(
                    select(RegressionDataset).where(
                        and_(
                            *self._dataset_scope(),
                            RegressionDataset.subject_kind == subject_kind,
                            RegressionDataset.subject_id == subject_id,
                            RegressionDataset.name == name,
                        )
                    )
                )
            ).first()
        )

    async def create_dataset(
        self,
        *,
        subject_kind: str,
        subject_id: str,
        name: str,
        description: str = "",
    ) -> RegressionDataset:
        """Create an empty dataset, or take over cases already filed under the name.

        Cases frozen from runs before datasets were objects carry only a name;
        creating the dataset they name keeps them rather than starting a second,
        empty set beside them.
        """
        name = self._clean_name(name)
        if await self.find_dataset(subject_kind=subject_kind, subject_id=subject_id, name=name):
            raise ConflictError(
                f"A dataset named '{name}' already exists for this agent",
                {"name": name, "subject_id": subject_id},
            )
        dataset, adopted = await self._open_dataset(
            subject_kind=subject_kind,
            subject_id=subject_id,
            name=name,
            description=self._clean_description(description),
        )
        self._audit(
            "evaluation.dataset.created", "create", dataset, {"adopted_cases": adopted}
        )
        await self.db.commit()
        return dataset

    async def update_dataset(
        self,
        dataset_id: str,
        *,
        description: str | None = None,
        status: str | None = None,
    ) -> RegressionDataset:
        """Change a dataset's description, or archive or restore it.

        Archiving takes its cases out of every run, the publish gate included;
        restoring puts back exactly those it took out. Neither changes the
        revision, since the cases themselves are not edited.
        """
        dataset = await self.get_dataset(dataset_id)
        changed: dict[str, Any] = {}
        if description is not None:
            cleaned = self._clean_description(description)
            if cleaned != dataset.description:
                dataset.description = cleaned
                changed["description"] = True
        operation = "update"
        event = "evaluation.dataset.updated"
        if status is not None and status != dataset.status:
            if status not in ("active", "archived"):
                raise ValidationError("A dataset's status is 'active' or 'archived'")
            await self._set_case_status(
                dataset,
                from_status="active" if status == "archived" else "archived",
                to_status="archived" if status == "archived" else "active",
            )
            dataset.status = status
            changed["status"] = status
            operation = "archive" if status == "archived" else "restore"
            event = f"evaluation.dataset.{'archived' if status == 'archived' else 'restored'}"
        if not changed:
            return dataset
        dataset.updated_at = utc_now()
        self.db.add(dataset)
        self._audit(event, operation, dataset, {"changed": sorted(changed)})
        await self.db.commit()
        return dataset

    # ------------------------------------------------------------------
    # Cases
    # ------------------------------------------------------------------

    async def list_cases(
        self,
        dataset: RegressionDataset,
        *,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RegressionCase]:
        conditions = self._active_case_conditions(dataset)
        if query:
            conditions.append(RegressionCase.name.ilike(f"%{query.strip()}%"))
        rows = (
            await self.db.exec(
                select(RegressionCase)
                .where(and_(*conditions))
                .order_by(RegressionCase.created_at, RegressionCase.id)
                .limit(max(1, min(limit, 200)))
                .offset(max(0, offset))
            )
        ).all()
        return [_unwrap(row) for row in rows]

    async def count_cases(self, dataset: RegressionDataset, *, query: str | None = None) -> int:
        conditions = self._active_case_conditions(dataset)
        if query:
            conditions.append(RegressionCase.name.ilike(f"%{query.strip()}%"))
        return int(
            (
                await self.db.exec(
                    select(func.count()).select_from(RegressionCase).where(and_(*conditions))
                )
            ).scalar_one()
        )

    async def get_case(self, dataset: RegressionDataset, case_id: str) -> RegressionCase:
        case = _unwrap(
            (
                await self.db.exec(
                    select(RegressionCase).where(
                        and_(
                            RegressionCase.id == case_id,
                            RegressionCase.status != "removed",
                            *self._case_scope(dataset),
                        )
                    )
                )
            ).first()
        )
        if case is None:
            raise NotFoundError(f"Case not found: {case_id}")
        return case

    async def add_case(
        self, dataset_id: str, document: dict[str, Any], *, note: str = ""
    ) -> RegressionCase:
        dataset = await self._writable(dataset_id)
        parsed = dataset_format.validate_case(document)
        existing = await self._active_cases(dataset)
        self._require_room(existing, 1)
        self._require_free_name(existing, parsed.name)
        revision = self._advance(dataset)
        case = self._new_case(dataset, parsed, revision)
        self.db.add(case)
        await self.db.flush()
        await self._write_version(dataset, note=note)
        self._audit(
            "evaluation.case.created",
            "create",
            dataset,
            {"case_id": case.id, "name": case.name},
            resource_type="regression_case",
            resource_id=case.id,
        )
        await self.db.commit()
        return case

    async def update_case(
        self, dataset_id: str, case_id: str, patch: dict[str, Any], *, note: str = ""
    ) -> RegressionCase:
        """Change a case's name, input or expectations, keeping its identity.

        The case keeps its id, so reports that already ran it still name it.
        """
        dataset = await self._writable(dataset_id)
        case = await self.get_case(dataset, case_id)
        current = dataset_format.case_document(
            case.name, case.input_snapshot_json, case.expected_features_json
        )
        merged = {**current, **{key: value for key, value in patch.items() if key in current}}
        parsed = dataset_format.validate_case(merged)
        if merged == current:
            return case
        existing = [item for item in await self._active_cases(dataset) if item.id != case.id]
        self._require_free_name(existing, parsed.name)
        revision = self._advance(dataset)
        case.name = parsed.name
        case.input_snapshot_json = parsed.input_snapshot
        case.expected_features_json = parsed.expected_features
        case.dataset_revision = revision
        self.db.add(case)
        await self.db.flush()
        await self._write_version(dataset, note=note)
        self._audit(
            "evaluation.case.updated",
            "update",
            dataset,
            {"case_id": case.id, "name": case.name},
            resource_type="regression_case",
            resource_id=case.id,
        )
        await self.db.commit()
        return case

    async def remove_case(self, dataset_id: str, case_id: str, *, note: str = "") -> RegressionDataset:
        """Take a case out of the set. Its row stays, so history that names it still reads."""
        dataset = await self._writable(dataset_id)
        case = await self.get_case(dataset, case_id)
        revision = self._advance(dataset)
        case.status = "removed"
        case.dataset_revision = revision
        self.db.add(case)
        await self.db.flush()
        await self._write_version(dataset, note=note)
        self._audit(
            "evaluation.case.removed",
            "remove",
            dataset,
            {"case_id": case.id, "name": case.name},
            resource_type="regression_case",
            resource_id=case.id,
        )
        await self.db.commit()
        return dataset

    async def import_cases(
        self, dataset_id: str, content: str, *, note: str = ""
    ) -> tuple[RegressionDataset, int]:
        """Add every case of a JSONL file, or none of them if any line is wrong."""
        dataset = await self._writable(dataset_id)
        parsed = dataset_format.parse_jsonl(content)
        existing = await self._active_cases(dataset)
        self._require_room(existing, len(parsed))
        taken = {case.name for case in existing}
        clashes = [item.name for item in parsed if item.name in taken]
        if clashes:
            raise ConflictError(
                f"{len(clashes)} case names already exist in this dataset; nothing was imported",
                {"names": clashes[:50], "error_count": len(clashes)},
            )
        revision = self._advance(dataset)
        # Cases list by creation time; spacing the file's cases a microsecond
        # apart keeps them in file order however coarse the clock is.
        started = utc_now()
        for index, item in enumerate(parsed):
            case = self._new_case(dataset, item, revision)
            case.created_at = started + timedelta(microseconds=index)
            self.db.add(case)
        await self.db.flush()
        await self._write_version(dataset, note=note or "Imported from JSONL")
        self._audit(
            "evaluation.dataset.imported",
            "import",
            dataset,
            {"imported": len(parsed)},
        )
        await self.db.commit()
        return dataset, len(parsed)

    async def export_cases(self, dataset_id: str) -> tuple[RegressionDataset, str]:
        """The dataset's active cases as JSONL, in the format import reads."""
        dataset = await self.get_dataset(dataset_id)
        cases = await self._active_cases(dataset)
        documents = [
            dataset_format.case_document(
                case.name, case.input_snapshot_json, case.expected_features_json
            )
            for case in cases
        ]
        self._audit(
            "evaluation.dataset.exported",
            "export",
            dataset,
            {"cases": len(documents), "format": "jsonl"},
        )
        await self.db.commit()
        return dataset, dataset_format.render_jsonl(documents)

    # ------------------------------------------------------------------
    # Versions
    # ------------------------------------------------------------------

    async def list_versions(
        self, dataset: RegressionDataset, *, limit: int = 100, offset: int = 0
    ) -> list[RegressionDatasetVersion]:
        """Versions newest first, without their snapshots."""
        rows = (
            await self.db.exec(
                select(
                    RegressionDatasetVersion.id,
                    RegressionDatasetVersion.tenant_id,
                    RegressionDatasetVersion.workspace_id,
                    RegressionDatasetVersion.dataset_id,
                    RegressionDatasetVersion.revision,
                    RegressionDatasetVersion.case_count,
                    RegressionDatasetVersion.content_hash,
                    RegressionDatasetVersion.changes_json,
                    RegressionDatasetVersion.note,
                    RegressionDatasetVersion.created_by,
                    RegressionDatasetVersion.created_at,
                )
                .where(
                    and_(
                        RegressionDatasetVersion.dataset_id == dataset.id,
                        *self._version_scope(),
                    )
                )
                .order_by(desc(RegressionDatasetVersion.revision))
                .limit(max(1, min(limit, 200)))
                .offset(max(0, offset))
            )
        ).all()
        return [
            RegressionDatasetVersion(
                id=row.id,
                tenant_id=row.tenant_id,
                workspace_id=row.workspace_id,
                dataset_id=row.dataset_id,
                revision=row.revision,
                case_count=row.case_count,
                content_hash=row.content_hash,
                changes_json=row.changes_json or {},
                note=row.note,
                created_by=row.created_by,
                created_at=row.created_at,
                snapshot_json=[],
            )
            for row in rows
        ]

    async def get_version(
        self, dataset: RegressionDataset, revision: int
    ) -> RegressionDatasetVersion:
        version = _unwrap(
            (
                await self.db.exec(
                    select(RegressionDatasetVersion).where(
                        and_(
                            RegressionDatasetVersion.dataset_id == dataset.id,
                            RegressionDatasetVersion.revision == revision,
                            *self._version_scope(),
                        )
                    )
                )
            ).first()
        )
        if version is None:
            raise NotFoundError(f"Dataset revision not found: {revision}")
        return version

    # ------------------------------------------------------------------
    # Cases frozen from runs
    # ------------------------------------------------------------------

    async def add_frozen_case(self, case: RegressionCase) -> RegressionCase:
        """File a case frozen from a run into its dataset and commit.

        The dataset is created if the case's name has none yet. A first case
        is part of the dataset's first revision; later ones advance it, which
        the case-from-run path never did before datasets existed.
        """
        dataset = await self.find_dataset(
            subject_kind=case.subject_kind, subject_id=case.subject_id, name=case.dataset
        )
        if dataset is not None and dataset.status != "active":
            raise ValidationError(
                f"The dataset '{dataset.name}' is archived; restore it to add cases",
                {"dataset_id": dataset.id},
            )
        if dataset is None:
            orphans = await self._orphan_cases(case.subject_kind, case.subject_id, case.dataset)
            if not orphans:
                dataset = RegressionDataset(
                    tenant_id=self.ctx.tenant_id,
                    workspace_id=self.ctx.workspace_id,
                    subject_kind=case.subject_kind,
                    subject_id=case.subject_id,
                    name=case.dataset,
                    revision=1,
                    created_by=self.ctx.user_id,
                )
                case.dataset_revision = 1
                self.db.add(dataset)
                self.db.add(case)
                await self.db.flush()
                await self._write_version(dataset, note="Created from a run")
                self._audit("evaluation.dataset.created", "create", dataset, {"from_run": True})
                self._audit(
                    "evaluation.case.created",
                    "create",
                    dataset,
                    {"case_id": case.id, "name": case.name, "source_run_id": case.source_run_id},
                    resource_type="regression_case",
                    resource_id=case.id,
                )
                await self.db.commit()
                return case
            dataset, _ = await self._open_dataset(
                subject_kind=case.subject_kind,
                subject_id=case.subject_id,
                name=case.dataset,
                description="",
            )
        revision = self._advance(dataset)
        case.dataset_revision = revision
        self.db.add(case)
        await self.db.flush()
        await self._write_version(dataset, note="Case frozen from a run")
        self._audit(
            "evaluation.case.created",
            "create",
            dataset,
            {"case_id": case.id, "name": case.name, "source_run_id": case.source_run_id},
            resource_type="regression_case",
            resource_id=case.id,
        )
        await self.db.commit()
        return case

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _open_dataset(
        self, *, subject_kind: str, subject_id: str, name: str, description: str
    ) -> tuple[RegressionDataset, int]:
        """Insert a dataset row and its first snapshot; also how many cases it took over."""
        orphans = await self._orphan_cases(subject_kind, subject_id, name)
        revision = max((int(case.dataset_revision or 1) for case in orphans), default=1)
        dataset = RegressionDataset(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            subject_kind=subject_kind,
            subject_id=subject_id,
            name=name,
            description=description,
            revision=revision,
            created_by=self.ctx.user_id,
        )
        self.db.add(dataset)
        await self.db.flush()
        await self._write_version(
            dataset, note="Took over existing cases" if orphans else "Created"
        )
        return dataset, len(orphans)

    async def _orphan_cases(
        self, subject_kind: str, subject_id: str, name: str
    ) -> list[RegressionCase]:
        rows = (
            await self.db.exec(
                select(RegressionCase).where(
                    and_(
                        RegressionCase.tenant_id == self.ctx.tenant_id,
                        RegressionCase.workspace_id == self.ctx.workspace_id,
                        RegressionCase.subject_kind == subject_kind,
                        RegressionCase.subject_id == subject_id,
                        RegressionCase.dataset == name,
                        RegressionCase.status == "active",
                    )
                )
            )
        ).all()
        return [_unwrap(row) for row in rows]

    async def _writable(self, dataset_id: str) -> RegressionDataset:
        dataset = await self.get_dataset(dataset_id)
        if dataset.status != "active":
            raise ValidationError(
                "The dataset is archived; restore it before changing its cases",
                {"dataset_id": dataset.id, "status": dataset.status},
            )
        return dataset

    def _advance(self, dataset: RegressionDataset) -> int:
        dataset.revision = int(dataset.revision or 1) + 1
        dataset.updated_at = utc_now()
        self.db.add(dataset)
        return dataset.revision

    async def _write_version(self, dataset: RegressionDataset, *, note: str) -> None:
        """Snapshot the set as it stands, at the dataset's current revision."""
        cases = await self._active_cases(dataset)
        snapshot = [
            dataset_format.case_document(
                case.name, case.input_snapshot_json, case.expected_features_json
            )
            for case in cases
        ]
        previous = _unwrap(
            (
                await self.db.exec(
                    select(RegressionDatasetVersion.snapshot_json)
                    .where(
                        and_(
                            RegressionDatasetVersion.dataset_id == dataset.id,
                            RegressionDatasetVersion.revision < dataset.revision,
                            *self._version_scope(),
                        )
                    )
                    .order_by(desc(RegressionDatasetVersion.revision))
                    .limit(1)
                )
            ).first()
        )
        changes = dataset_format.diff_snapshots(previous or [], snapshot)
        self.db.add(
            RegressionDatasetVersion(
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                dataset_id=dataset.id,
                revision=dataset.revision,
                case_count=len(snapshot),
                content_hash=dataset_format.content_hash(snapshot),
                snapshot_json=snapshot,
                changes_json=changes,
                note=(note or "").strip()[:MAX_NOTE_LENGTH],
                created_by=self.ctx.user_id,
            )
        )

    async def _active_cases(self, dataset: RegressionDataset) -> list[RegressionCase]:
        rows = (
            await self.db.exec(
                select(RegressionCase)
                .where(and_(*self._active_case_conditions(dataset)))
                .order_by(RegressionCase.created_at, RegressionCase.id)
            )
        ).all()
        return [_unwrap(row) for row in rows]

    async def _set_case_status(
        self, dataset: RegressionDataset, *, from_status: str, to_status: str
    ) -> None:
        rows = (
            await self.db.exec(
                select(RegressionCase).where(
                    and_(*self._case_scope(dataset), RegressionCase.status == from_status)
                )
            )
        ).all()
        for row in rows:
            case = _unwrap(row)
            case.status = to_status
            self.db.add(case)

    async def _summarise(self, dataset: RegressionDataset) -> DatasetSummary:
        count = await self.count_cases(dataset)
        report = _unwrap(
            (
                await self.db.exec(
                    select(RegressionReport)
                    .where(
                        and_(
                            RegressionReport.tenant_id == self.ctx.tenant_id,
                            RegressionReport.workspace_id == self.ctx.workspace_id,
                            RegressionReport.subject_kind == dataset.subject_kind,
                            RegressionReport.subject_id == dataset.subject_id,
                            RegressionReport.dataset == dataset.name,
                        )
                    )
                    .order_by(desc(RegressionReport.created_at))
                    .limit(1)
                )
            ).first()
        )
        return DatasetSummary(dataset=dataset, case_count=count, latest_report=report)

    def _new_case(
        self, dataset: RegressionDataset, document: DatasetCaseDocument, revision: int
    ) -> RegressionCase:
        return RegressionCase(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            subject_kind=dataset.subject_kind,
            subject_id=dataset.subject_id,
            source_run_id=None,
            name=document.name,
            dataset=dataset.name,
            dataset_revision=revision,
            input_snapshot_json=document.input_snapshot,
            expected_features_json=document.expected_features,
            created_by=self.ctx.user_id,
        )

    def _audit(
        self,
        event_type: str,
        operation: str,
        dataset: RegressionDataset,
        payload: dict[str, Any],
        *,
        resource_type: str = "regression_dataset",
        resource_id: str | None = None,
    ) -> None:
        self.db.add(
            AuditEvent(
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                event_type=event_type,
                resource_type=resource_type,
                resource_id=resource_id or dataset.id,
                operation=operation,
                actor_user_id=self.ctx.user_id,
                trace_id=getattr(self.ctx, "trace_id", None),
                outcome="allowed",
                scope="workspace",
                payload_json={
                    "dataset_id": dataset.id,
                    "dataset": dataset.name,
                    "subject_kind": dataset.subject_kind,
                    "subject_id": dataset.subject_id,
                    "revision": dataset.revision,
                    "api_key_id": getattr(self.ctx, "api_key_id", None),
                    **payload,
                },
            )
        )

    def _dataset_scope(self) -> list[Any]:
        return [
            RegressionDataset.tenant_id == self.ctx.tenant_id,
            RegressionDataset.workspace_id == self.ctx.workspace_id,
        ]

    def _version_scope(self) -> list[Any]:
        return [
            RegressionDatasetVersion.tenant_id == self.ctx.tenant_id,
            RegressionDatasetVersion.workspace_id == self.ctx.workspace_id,
        ]

    def _case_scope(self, dataset: RegressionDataset) -> list[Any]:
        return [
            RegressionCase.tenant_id == self.ctx.tenant_id,
            RegressionCase.workspace_id == self.ctx.workspace_id,
            RegressionCase.subject_kind == dataset.subject_kind,
            RegressionCase.subject_id == dataset.subject_id,
            RegressionCase.dataset == dataset.name,
        ]

    def _active_case_conditions(self, dataset: RegressionDataset) -> list[Any]:
        return [*self._case_scope(dataset), RegressionCase.status == "active"]

    @staticmethod
    def _require_free_name(existing: list[RegressionCase], name: str) -> None:
        if any(case.name == name for case in existing):
            raise ConflictError(
                f"A case named '{name}' already exists in this dataset", {"name": name}
            )

    @staticmethod
    def _require_room(existing: list[RegressionCase], adding: int) -> None:
        if len(existing) + adding > MAX_ACTIVE_CASES:
            raise ValidationError(
                f"A dataset holds at most {MAX_ACTIVE_CASES} cases",
                {"max_cases": MAX_ACTIVE_CASES},
            )

    @staticmethod
    def _clean_name(name: str) -> str:
        cleaned = (name or "").strip()
        if not cleaned:
            raise ValidationError("A dataset needs a name")
        if len(cleaned) > MAX_NAME_LENGTH:
            raise ValidationError(f"A dataset name is at most {MAX_NAME_LENGTH} characters")
        return cleaned

    @staticmethod
    def _clean_description(description: str) -> str:
        cleaned = (description or "").strip()
        if len(cleaned) > MAX_DESCRIPTION_LENGTH:
            raise ValidationError(
                f"A description is at most {MAX_DESCRIPTION_LENGTH} characters"
            )
        return cleaned

