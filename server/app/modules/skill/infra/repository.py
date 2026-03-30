"""Skill repositories."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.modules.skill.domain.models import Skill, SkillPublish, SkillVersion


class SkillRepository:
    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def create(self, skill: Skill) -> Skill:
        skill.tenant_id = self.ctx.tenant_id
        skill.workspace_id = self.ctx.workspace_id
        skill.created_by = skill.created_by or self.ctx.user_id
        skill.updated_by = skill.updated_by or self.ctx.user_id
        self.db.add(skill)
        self.db.commit()
        self.db.refresh(skill)
        return skill

    def update(self, skill: Skill) -> Skill:
        skill.updated_at = utc_now()
        skill.updated_by = self.ctx.user_id
        self.db.add(skill)
        self.db.commit()
        self.db.refresh(skill)
        return skill

    def get_by_id(self, skill_id: str) -> Optional[Skill]:
        query = select(Skill).where(
            and_(
                Skill.id == skill_id,
                Skill.tenant_id == self.ctx.tenant_id,
                Skill.workspace_id == self.ctx.workspace_id,
                Skill.deleted_at.is_(None),
            )
        )
        return self.db.execute(query).scalars().first()

    def get_by_name(self, name: str) -> Optional[Skill]:
        query = select(Skill).where(
            and_(
                Skill.name == name,
                Skill.tenant_id == self.ctx.tenant_id,
                Skill.workspace_id == self.ctx.workspace_id,
                Skill.deleted_at.is_(None),
            )
        )
        return self.db.execute(query).scalars().first()

    def list(self, *, limit: int, offset: int) -> list[Skill]:
        query = (
            select(Skill)
            .where(
                and_(
                    Skill.tenant_id == self.ctx.tenant_id,
                    Skill.workspace_id == self.ctx.workspace_id,
                    Skill.deleted_at.is_(None),
                    Skill.status != "archived",
                )
            )
            .order_by(desc(Skill.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.execute(query).scalars().all())

    def next_version_number(self, skill_id: str) -> int:
        query = select(func.max(SkillVersion.version)).where(
            and_(
                SkillVersion.skill_id == skill_id,
                SkillVersion.tenant_id == self.ctx.tenant_id,
                SkillVersion.workspace_id == self.ctx.workspace_id,
            )
        )
        return int(self.db.execute(query).scalar_one_or_none() or 0) + 1


class SkillVersionRepository:
    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def create(self, version: SkillVersion) -> SkillVersion:
        version.tenant_id = self.ctx.tenant_id
        version.workspace_id = self.ctx.workspace_id
        version.created_by = version.created_by or self.ctx.user_id
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version

    def update(self, version: SkillVersion) -> SkillVersion:
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version

    def get_by_id(self, version_id: str) -> Optional[SkillVersion]:
        query = select(SkillVersion).where(
            and_(
                SkillVersion.id == version_id,
                SkillVersion.tenant_id == self.ctx.tenant_id,
                SkillVersion.workspace_id == self.ctx.workspace_id,
            )
        )
        return self.db.execute(query).scalars().first()

    def list_by_skill(self, skill_id: str, *, limit: int, offset: int) -> list[SkillVersion]:
        query = (
            select(SkillVersion)
            .where(
                and_(
                    SkillVersion.skill_id == skill_id,
                    SkillVersion.tenant_id == self.ctx.tenant_id,
                    SkillVersion.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(desc(SkillVersion.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.execute(query).scalars().all())


class SkillPublishRepository:
    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def create(self, publish: SkillPublish) -> SkillPublish:
        publish.tenant_id = self.ctx.tenant_id
        publish.workspace_id = self.ctx.workspace_id
        publish.created_by = publish.created_by or self.ctx.user_id
        self.db.add(publish)
        self.db.commit()
        self.db.refresh(publish)
        return publish

    def list_by_skill(self, skill_id: str) -> list[SkillPublish]:
        query = (
            select(SkillPublish)
            .where(
                and_(
                    SkillPublish.skill_id == skill_id,
                    SkillPublish.tenant_id == self.ctx.tenant_id,
                    SkillPublish.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(desc(SkillPublish.created_at))
        )
        return list(self.db.execute(query).scalars().all())
