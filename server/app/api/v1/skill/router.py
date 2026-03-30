"""Skill API routes."""

from typing import Optional

from fastapi import APIRouter, Depends, status

from app.api.v1.permissions import require_workspace_read_ctx, require_workspace_write_ctx
from app.api.v1.skill.dependencies import get_skill_service
from app.api.v1.skill.handlers import SkillHandlers
from app.infra.db.pagination import PaginatedResponse
from app.kernel.contracts.context import RequestContext
from app.modules.skill.application.schemas import (
    SkillCreate,
    SkillPublishRequest,
    SkillReleaseResponse,
    SkillRollbackRequest,
    SkillResponse,
    SkillUpdate,
    SkillVersionCreate,
    SkillVersionResponse,
)
from app.modules.skill.application.service import SkillService


router = APIRouter()


@router.post("", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(
    payload: SkillCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: SkillService = Depends(get_skill_service),
):
    return await SkillHandlers(service).create_skill(ctx, payload)


@router.get("", response_model=PaginatedResponse[SkillResponse])
async def list_skills(
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: SkillService = Depends(get_skill_service),
):
    return await SkillHandlers(service).list_skills(ctx, page_token=page_token, page_size=page_size)


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: SkillService = Depends(get_skill_service),
):
    return await SkillHandlers(service).get_skill(ctx, skill_id)


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str,
    payload: SkillUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: SkillService = Depends(get_skill_service),
):
    return await SkillHandlers(service).update_skill(ctx, skill_id, payload)


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: SkillService = Depends(get_skill_service),
):
    await SkillHandlers(service).delete_skill(ctx, skill_id)


@router.post("/{skill_id}/versions", response_model=SkillVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_skill_version(
    skill_id: str,
    payload: SkillVersionCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: SkillService = Depends(get_skill_service),
):
    return await SkillHandlers(service).create_version(ctx, skill_id, payload)


@router.get("/{skill_id}/versions", response_model=PaginatedResponse[SkillVersionResponse])
async def list_skill_versions(
    skill_id: str,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: SkillService = Depends(get_skill_service),
):
    return await SkillHandlers(service).list_versions(ctx, skill_id, page_token=page_token, page_size=page_size)


@router.get("/{skill_id}/releases", response_model=PaginatedResponse[SkillReleaseResponse])
async def list_skill_releases(
    skill_id: str,
    page_token: Optional[str] = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: SkillService = Depends(get_skill_service),
):
    return await SkillHandlers(service).list_releases(ctx, skill_id, page_token=page_token, page_size=page_size)


@router.post("/{skill_id}/publish", response_model=SkillResponse)
async def publish_skill_version(
    skill_id: str,
    payload: SkillPublishRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: SkillService = Depends(get_skill_service),
):
    return await SkillHandlers(service).publish_version(ctx, skill_id, payload)


@router.post("/{skill_id}/rollback", response_model=SkillResponse)
async def rollback_skill_version(
    skill_id: str,
    payload: SkillRollbackRequest,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: SkillService = Depends(get_skill_service),
):
    return await SkillHandlers(service).rollback_version(ctx, skill_id, payload)
