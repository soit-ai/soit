"""Skill application service."""

from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.guard import workspace_guard
from app.modules.skill.application.schemas import SkillCreate, SkillUpdate, SkillVersionCreate
from app.modules.skill.application.versioning_adapter import SkillVersioningAdapter
from app.modules.skill.domain.models import Skill, SkillPublish, SkillVersion
from app.modules.skill.infra.repository import SkillPublishRepository, SkillRepository, SkillVersionRepository
from app.modules.versioning.application.service import VersionControlService


class SkillService:
    """CRUD and publish operations for skills."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx
        self.skill_repo = SkillRepository(db, ctx)
        self.version_repo = SkillVersionRepository(db, ctx)
        self.publish_repo = SkillPublishRepository(db, ctx)
        self.versioning = VersionControlService(
            SkillVersioningAdapter(
                skill_repo=self.skill_repo,
                version_repo=self.version_repo,
                publish_repo=self.publish_repo,
            )
        )

    def _get_skill(self, skill_id: str) -> Skill:
        skill = self.skill_repo.get_by_id(skill_id)
        if not skill:
            raise NotFoundError(f"Skill not found: {skill_id}")
        return skill

    @workspace_guard("write")
    async def create_skill(self, data: SkillCreate) -> Skill:
        existing = self.skill_repo.get_by_name(data.name)
        if existing:
            raise ValidationError(f"Skill with name '{data.name}' already exists")
        skill = self.skill_repo.create(
            Skill(
                name=data.name,
                description=data.description,
                category=data.category,
                visibility=data.visibility,
                metadata_json=data.metadata_json,
            )
        )
        await self.create_version(
            skill.id,
            SkillVersionCreate(spec_json=data.spec_json),
        )
        return self._get_skill(skill.id)

    @workspace_guard("read")
    async def list_skills(self, limit: int = 20, offset: int = 0) -> List[Skill]:
        return self.skill_repo.list(limit=limit, offset=offset)

    @workspace_guard("read")
    async def get_skill(self, skill_id: str) -> Skill:
        return self._get_skill(skill_id)

    @workspace_guard("write")
    async def update_skill(self, skill_id: str, data: SkillUpdate) -> Skill:
        skill = self._get_skill(skill_id)
        if data.name and data.name != skill.name:
            existing = self.skill_repo.get_by_name(data.name)
            if existing and existing.id != skill.id:
                raise ValidationError(f"Skill with name '{data.name}' already exists")
            skill.name = data.name
        if data.description is not None:
            skill.description = data.description
        if data.category is not None:
            skill.category = data.category
        if data.status is not None:
            skill.status = data.status
        if data.visibility is not None:
            skill.visibility = data.visibility
        if data.metadata_json is not None:
            skill.metadata_json = data.metadata_json
        return self.skill_repo.update(skill)

    @workspace_guard("write")
    async def delete_skill(self, skill_id: str) -> None:
        skill = self._get_skill(skill_id)
        skill.status = "archived"
        skill.deleted_at = utc_now()
        self.skill_repo.update(skill)

    @workspace_guard("write")
    async def create_version(self, skill_id: str, data: SkillVersionCreate) -> SkillVersion:
        return self.versioning.create_draft(
            skill_id,
            spec_schema="skill.v1",
            spec_json=data.spec_json,
        )

    @workspace_guard("read")
    async def list_versions(self, skill_id: str, limit: int = 20, offset: int = 0) -> List[SkillVersion]:
        return self.versioning.list_versions(skill_id, limit=limit, offset=offset)

    @workspace_guard("read")
    async def list_releases(self, skill_id: str, limit: int = 20, offset: int = 0) -> List[SkillPublish]:
        return self.versioning.list_releases(skill_id, limit=limit, offset=offset)

    @workspace_guard("write")
    async def publish_version(self, skill_id: str, version_id: str, *, notes: str | None = None) -> Skill:
        return self.versioning.publish(skill_id, version_id, notes=notes)

    @workspace_guard("write")
    async def rollback_version(self, skill_id: str, version_id: str, *, notes: str | None = None) -> Skill:
        return self.versioning.rollback(skill_id, version_id, notes=notes)
