"""Handlers for skill APIs."""

from __future__ import annotations

from typing import Optional

from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.contracts.context import RequestContext
from app.modules.skill.application.schemas import (
    SkillCreate,
    SkillPublishRequest,
    SkillResponse,
    SkillUpdate,
    SkillVersionCreate,
    SkillVersionResponse,
)
from app.modules.skill.application.service import SkillService


class SkillHandlers:
    def __init__(self, service: SkillService) -> None:
        self.service = service

    async def create_skill(self, ctx: RequestContext, payload: SkillCreate) -> SkillResponse:
        return SkillResponse.model_validate(await self.service.create_skill(payload))

    async def list_skills(
        self,
        ctx: RequestContext,
        *,
        page_token: Optional[str],
        page_size: int,
    ) -> PaginatedResponse[SkillResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        skills = await self.service.list_skills(limit=limit, offset=offset)
        items = [SkillResponse.model_validate(item) for item in skills]
        has_next = len(skills) == limit
        next_offset = offset + len(skills) if has_next else None
        return PaginatedResponse.create(items=items, page_size=len(items), has_next=has_next, next_offset=next_offset)

    async def get_skill(self, ctx: RequestContext, skill_id: str) -> SkillResponse:
        return SkillResponse.model_validate(await self.service.get_skill(skill_id))

    async def update_skill(self, ctx: RequestContext, skill_id: str, payload: SkillUpdate) -> SkillResponse:
        return SkillResponse.model_validate(await self.service.update_skill(skill_id, payload))

    async def delete_skill(self, ctx: RequestContext, skill_id: str) -> None:
        await self.service.delete_skill(skill_id)

    async def create_version(
        self,
        ctx: RequestContext,
        skill_id: str,
        payload: SkillVersionCreate,
    ) -> SkillVersionResponse:
        return SkillVersionResponse.model_validate(await self.service.create_version(skill_id, payload))

    async def list_versions(
        self,
        ctx: RequestContext,
        skill_id: str,
        *,
        page_token: Optional[str],
        page_size: int,
    ) -> PaginatedResponse[SkillVersionResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        versions = await self.service.list_versions(skill_id, limit=limit, offset=offset)
        items = [SkillVersionResponse.model_validate(item) for item in versions]
        has_next = len(versions) == limit
        next_offset = offset + len(versions) if has_next else None
        return PaginatedResponse.create(items=items, page_size=len(items), has_next=has_next, next_offset=next_offset)

    async def publish_version(
        self,
        ctx: RequestContext,
        skill_id: str,
        payload: SkillPublishRequest,
    ) -> SkillResponse:
        return SkillResponse.model_validate(await self.service.publish_version(skill_id, payload.version_id))
