"""Shared versioning and release orchestration."""

from __future__ import annotations

from typing import Any, Optional

from app.kernel.commons.errors import NotFoundError


class VersioningAdapter:
    """Base adapter for subject-specific version and release persistence."""

    subject_kind = "subject"

    def get_subject(self, subject_id: str) -> Any | None:
        raise NotImplementedError

    def get_version(self, version_id: str) -> Any | None:
        raise NotImplementedError

    def version_matches_subject(self, version: Any, subject_id: str) -> bool:
        raise NotImplementedError

    def next_version_number(self, subject_id: str) -> int:
        raise NotImplementedError

    def create_version(
        self,
        subject_id: str,
        *,
        version_no: int,
        spec_schema: str,
        spec_json: dict[str, Any],
        based_on_version_id: Optional[str],
        metadata: Optional[dict[str, Any]],
    ) -> Any:
        raise NotImplementedError

    def update_version(self, version: Any) -> Any:
        raise NotImplementedError

    def update_head(self, subject: Any, version: Any) -> Any:
        raise NotImplementedError

    def update_live(self, subject: Any, version: Any) -> Any:
        raise NotImplementedError

    def create_release(
        self,
        subject: Any,
        version: Any,
        *,
        scope: str,
        status: str,
        notes: Optional[str],
        previous_live_version_id: Optional[str],
        rollback_of_publish_id: Optional[str] = None,
    ) -> Any:
        raise NotImplementedError

    def list_versions(self, subject_id: str, *, limit: int, offset: int) -> list[Any]:
        raise NotImplementedError

    def list_releases(self, subject_id: str, *, limit: int, offset: int) -> list[Any]:
        raise NotImplementedError

    def find_release_id_for_version(self, subject_id: str, version_id: str | None) -> str | None:
        return None

    def validate_for_draft(
        self,
        subject: Any,
        *,
        spec_schema: str,
        spec_json: dict[str, Any],
        metadata: Optional[dict[str, Any]],
    ) -> None:
        return None

    def validate_for_publish(self, subject: Any, version: Any) -> None:
        return None

    def validate_for_rollback(self, subject: Any, version: Any) -> None:
        return None

    def after_version_created(self, subject: Any, version: Any) -> None:
        return None

    def after_publish(self, subject: Any, version: Any, release: Any) -> None:
        return None

    def after_rollback(self, subject: Any, version: Any, release: Any) -> None:
        return None


class VersionControlService:
    """Shared orchestration for draft, publish, rollback, and version lookup."""

    def __init__(self, adapter: VersioningAdapter) -> None:
        self.adapter = adapter

    def _get_subject(self, subject_id: str) -> Any:
        subject = self.adapter.get_subject(subject_id)
        if subject is None:
            raise NotFoundError(f"{self.adapter.subject_kind} not found: {subject_id}")
        return subject

    def _get_version_for_subject(self, subject_id: str, version_id: str) -> tuple[Any, Any]:
        subject = self._get_subject(subject_id)
        version = self.adapter.get_version(version_id)
        if version is None or not self.adapter.version_matches_subject(version, subject_id):
            raise NotFoundError(f"{self.adapter.subject_kind} version not found: {version_id}")
        return subject, version

    def create_draft(
        self,
        subject_id: str,
        *,
        spec_schema: str,
        spec_json: dict[str, Any],
        based_on_version_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Any:
        subject = self._get_subject(subject_id)
        resolved_based_on = based_on_version_id
        if resolved_based_on is None:
            resolved_based_on = getattr(subject, "current_version_id", None)

        self.adapter.validate_for_draft(
            subject,
            spec_schema=spec_schema,
            spec_json=spec_json,
            metadata=metadata,
        )
        version = self.adapter.create_version(
            subject_id,
            version_no=self.adapter.next_version_number(subject_id),
            spec_schema=spec_schema,
            spec_json=spec_json,
            based_on_version_id=resolved_based_on,
            metadata=metadata,
        )
        self.adapter.after_version_created(subject, version)
        self.adapter.update_head(subject, version)
        return version

    def publish(
        self,
        subject_id: str,
        version_id: str,
        *,
        scope: str = "workspace",
        notes: Optional[str] = None,
    ) -> Any:
        subject, version = self._get_version_for_subject(subject_id, version_id)
        self.adapter.validate_for_publish(subject, version)
        version.status = "published"
        self.adapter.update_version(version)
        release = self.adapter.create_release(
            subject,
            version,
            scope=scope,
            status="published",
            notes=notes,
            previous_live_version_id=getattr(subject, "published_version_id", None),
        )
        subject = self.adapter.update_live(subject, version)
        self.adapter.after_publish(subject, version, release)
        return subject

    def rollback(
        self,
        subject_id: str,
        version_id: str,
        *,
        scope: str = "workspace",
        notes: Optional[str] = None,
        rollback_of_publish_id: Optional[str] = None,
    ) -> Any:
        subject, version = self._get_version_for_subject(subject_id, version_id)
        self.adapter.validate_for_rollback(subject, version)
        version.status = "published"
        self.adapter.update_version(version)
        previous_live_version_id = getattr(subject, "published_version_id", None)
        resolved_rollback_of_publish_id = rollback_of_publish_id
        if resolved_rollback_of_publish_id is None and previous_live_version_id:
            resolved_rollback_of_publish_id = self.adapter.find_release_id_for_version(subject_id, previous_live_version_id)
        release = self.adapter.create_release(
            subject,
            version,
            scope=scope,
            status="rolled_back",
            notes=notes,
            previous_live_version_id=previous_live_version_id,
            rollback_of_publish_id=resolved_rollback_of_publish_id,
        )
        subject = self.adapter.update_live(subject, version)
        self.adapter.after_rollback(subject, version, release)
        return subject

    def get_head_version(self, subject_id: str) -> Any | None:
        subject = self._get_subject(subject_id)
        version_id = getattr(subject, "current_version_id", None)
        if not version_id:
            return None
        version = self.adapter.get_version(version_id)
        if version is None or not self.adapter.version_matches_subject(version, subject_id):
            return None
        return version

    def get_live_version(self, subject_id: str) -> Any | None:
        subject = self._get_subject(subject_id)
        version_id = getattr(subject, "published_version_id", None)
        if not version_id:
            return None
        version = self.adapter.get_version(version_id)
        if version is None or not self.adapter.version_matches_subject(version, subject_id):
            return None
        return version

    def list_versions(self, subject_id: str, *, limit: int, offset: int) -> list[Any]:
        self._get_subject(subject_id)
        return self.adapter.list_versions(subject_id, limit=limit, offset=offset)

    def list_releases(self, subject_id: str, *, limit: int, offset: int) -> list[Any]:
        self._get_subject(subject_id)
        return self.adapter.list_releases(subject_id, limit=limit, offset=offset)
