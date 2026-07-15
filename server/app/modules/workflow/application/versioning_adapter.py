"""Workflow-specific versioning adapter."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.modules.versioning.application.service import VersioningAdapter
from app.modules.workflow.domain.models import WorkflowPublish, WorkflowVersion
from app.modules.workflow.infra.repository import (
    WorkflowPublishRepository,
    WorkflowRepository,
    WorkflowVersionRepository,
)


class WorkflowVersioningAdapter(VersioningAdapter):
    """Persist shared versioning actions onto Workflow tables."""

    subject_kind = "workflow"

    def __init__(
        self,
        *,
        workflow_repo: WorkflowRepository,
        version_repo: WorkflowVersionRepository,
        publish_repo: WorkflowPublishRepository,
        validate_spec: Callable[[dict[str, Any]], None],
    ) -> None:
        self.workflow_repo = workflow_repo
        self.version_repo = version_repo
        self.publish_repo = publish_repo
        self.validate_spec_callback = validate_spec

    def get_subject(self, subject_id: str) -> Any | None:
        return self.workflow_repo.get_by_id(subject_id)

    def get_version(self, version_id: str) -> WorkflowVersion | None:
        return self.version_repo.get_by_id(version_id)

    def version_matches_subject(self, version: WorkflowVersion, subject_id: str) -> bool:
        return version.workflow_id == subject_id

    def next_version_number(self, subject_id: str) -> int:
        return self.workflow_repo.next_version_number(subject_id)

    def create_version(
        self,
        subject_id: str,
        *,
        version_no: int,
        spec_schema: str,
        spec_json: dict[str, Any],
        based_on_version_id: str | None,
        metadata: dict[str, Any] | None,
    ) -> WorkflowVersion:
        payload = metadata or {}
        return self.version_repo.create(
            WorkflowVersion(
                workflow_id=subject_id,
                version=version_no,
                status="draft",
                spec_schema=spec_schema,
                spec_json=spec_json,
                created_from_version_id=based_on_version_id,
                created_by=payload.get("created_by"),
            )
        )

    def update_version(self, version: WorkflowVersion) -> WorkflowVersion:
        return self.version_repo.update(version)

    def update_head(self, subject: Any, version: WorkflowVersion) -> Any:
        subject.current_version_id = version.id
        return self.workflow_repo.update(subject)

    def update_live(self, subject: Any, version: WorkflowVersion) -> Any:
        subject.published_version_id = version.id
        return self.workflow_repo.update(subject)

    def create_release(
        self,
        subject: Any,
        version: WorkflowVersion,
        *,
        scope: str,
        status: str,
        notes: str | None,
        previous_live_version_id: str | None,
        rollback_of_publish_id: str | None = None,
    ) -> Any:
        return self.publish_repo.create(
            WorkflowPublish(
                workflow_id=subject.id,
                workflow_version_id=version.id,
                action="rollback" if status == "rolled_back" else "publish",
                scope=scope,
                status=status,
                from_version_id=previous_live_version_id,
                to_version_id=version.id,
                notes=notes,
                rollback_of_publish_id=rollback_of_publish_id,
            )
        )

    def list_versions(self, subject_id: str, *, limit: int, offset: int) -> list[Any]:
        return self.version_repo.list_by_workflow(subject_id, limit=limit, offset=offset)

    def list_releases(self, subject_id: str, *, limit: int, offset: int) -> list[Any]:
        releases = self.publish_repo.list_by_workflow(subject_id)
        return releases[offset : offset + limit]

    def find_release_id_for_version(self, subject_id: str, version_id: str | None) -> str | None:
        if not version_id:
            return None
        for release in self.publish_repo.list_by_workflow(subject_id):
            if release.workflow_version_id == version_id or release.to_version_id == version_id:
                return release.id
        return None

    def validate_for_draft(
        self,
        subject: Any,
        *,
        spec_schema: str,
        spec_json: dict[str, Any],
        metadata: dict[str, Any] | None,
    ) -> None:
        self.validate_spec_callback(spec_json)

    def validate_for_publish(self, subject: Any, version: WorkflowVersion) -> None:
        self.validate_spec_callback(version.spec_json)

    def validate_for_rollback(self, subject: Any, version: WorkflowVersion) -> None:
        self.validate_spec_callback(version.spec_json)
