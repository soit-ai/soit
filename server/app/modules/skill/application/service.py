"""Skill application service."""

from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.guard import workspace_guard
from app.modules.skill.application.schemas import SkillCreate, SkillUpdate, SkillVersionCreate
from app.modules.skill.domain.models import Skill, SkillPublish, SkillVersion
from app.modules.skill.infra.repository import SkillPublishRepository, SkillRepository, SkillVersionRepository


class SkillService:
    """CRUD and publish operations for skills."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx
        self.skill_repo = SkillRepository(db, ctx)
        self.version_repo = SkillVersionRepository(db, ctx)
        self.publish_repo = SkillPublishRepository(db, ctx)

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
        version = self.version_repo.create(
            SkillVersion(
                skill_id=skill.id,
                version=self.skill_repo.next_version_number(skill.id),
                spec_json=data.spec_json,
            )
        )
        skill.current_version_id = version.id
        self.skill_repo.update(skill)
        return skill

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
        self._get_skill(skill_id)
        return self.version_repo.create(
            SkillVersion(
                skill_id=skill_id,
                version=self.skill_repo.next_version_number(skill_id),
                spec_json=data.spec_json,
            )
        )

    @workspace_guard("read")
    async def list_versions(self, skill_id: str, limit: int = 20, offset: int = 0) -> List[SkillVersion]:
        self._get_skill(skill_id)
        return self.version_repo.list_by_skill(skill_id, limit=limit, offset=offset)

    @workspace_guard("write")
    async def publish_version(self, skill_id: str, version_id: str) -> Skill:
        skill = self._get_skill(skill_id)
        version = self.version_repo.get_by_id(version_id)
        if not version or version.skill_id != skill.id:
            raise NotFoundError(f"Skill version not found: {version_id}")
        version.status = "published"
        self.version_repo.update(version)
        self.publish_repo.create(SkillPublish(skill_id=skill.id, skill_version_id=version.id))
        skill.current_version_id = version.id
        skill.published_version_id = version.id
        self.skill_repo.update(skill)
        return skill
