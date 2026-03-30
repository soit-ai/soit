"""Skill-specific versioning adapter."""

from __future__ import annotations

from typing import Any, Optional

from app.modules.skill.domain.models import SkillPublish, SkillVersion
from app.modules.skill.infra.repository import SkillPublishRepository, SkillRepository, SkillVersionRepository
from app.modules.versioning.application.service import VersioningAdapter


class SkillVersioningAdapter(VersioningAdapter):
    """Persist shared versioning actions onto Skill tables."""

    subject_kind = "skill"

    def __init__(
        self,
        *,
        skill_repo: SkillRepository,
        version_repo: SkillVersionRepository,
        publish_repo: SkillPublishRepository,
    ) -> None:
        self.skill_repo = skill_repo
        self.version_repo = version_repo
        self.publish_repo = publish_repo

    def get_subject(self, subject_id: str) -> Any | None:
        return self.skill_repo.get_by_id(subject_id)

    def get_version(self, version_id: str) -> SkillVersion | None:
        return self.version_repo.get_by_id(version_id)

    def version_matches_subject(self, version: SkillVersion, subject_id: str) -> bool:
        return version.skill_id == subject_id

    def next_version_number(self, subject_id: str) -> int:
        return self.skill_repo.next_version_number(subject_id)

    def create_version(
        self,
        subject_id: str,
        *,
        version_no: int,
        spec_schema: str,
        spec_json: dict[str, Any],
        based_on_version_id: Optional[str],
        metadata: Optional[dict[str, Any]],
    ) -> SkillVersion:
        return self.version_repo.create(
            SkillVersion(
                skill_id=subject_id,
                version=version_no,
                status="draft",
                spec_schema=spec_schema,
                spec_json=spec_json,
            )
        )

    def update_version(self, version: SkillVersion) -> SkillVersion:
        return self.version_repo.update(version)

    def update_head(self, subject: Any, version: SkillVersion) -> Any:
        subject.current_version_id = version.id
        return self.skill_repo.update(subject)

    def update_live(self, subject: Any, version: SkillVersion) -> Any:
        subject.published_version_id = version.id
        return self.skill_repo.update(subject)

    def create_release(
        self,
        subject: Any,
        version: SkillVersion,
        *,
        scope: str,
        status: str,
        notes: Optional[str],
        previous_live_version_id: Optional[str],
        rollback_of_publish_id: Optional[str] = None,
    ) -> Any:
        return self.publish_repo.create(
            SkillPublish(
                skill_id=subject.id,
                skill_version_id=version.id,
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
        return self.version_repo.list_by_skill(subject_id, limit=limit, offset=offset)

    def list_releases(self, subject_id: str, *, limit: int, offset: int) -> list[Any]:
        releases = self.publish_repo.list_by_skill(subject_id)
        return releases[offset : offset + limit]

    def find_release_id_for_version(self, subject_id: str, version_id: str | None) -> str | None:
        if not version_id:
            return None
        for release in self.publish_repo.list_by_skill(subject_id):
            if release.skill_version_id == version_id or release.to_version_id == version_id:
                return release.id
        return None
