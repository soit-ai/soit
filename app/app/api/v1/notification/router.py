""" router

Notification API routes.
"""

from typing import Optional

from fastapi import APIRouter, Depends, status

from app.kernel.contracts.context import RequestContext
from app.api.v1.permissions import require_workspace_read_ctx, require_workspace_write_ctx
from app.infra.db.pagination import PaginatedResponse
from app.modules.notification.application.schemas import (
    NotificationCreate,
    NotificationResponse,
    NotificationReadRequest,
    NotificationUnreadCount,
    NotificationBulkResult,
)
from app.modules.notification.application.service import NotificationService
from app.api.v1.notification.dependencies import get_notification_service
from app.api.v1.notification.handlers import NotificationHandlers


router = APIRouter()


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    data: NotificationCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: NotificationService = Depends(get_notification_service),
):
    handlers = NotificationHandlers(service)
    return await handlers.create_notification(ctx, data)


@router.get("", response_model=PaginatedResponse[NotificationResponse])
async def list_notifications(
    page_token: Optional[str] = None,
    page_size: int = 20,
    status: Optional[str] = None,
    type: Optional[str] = None,
    severity: Optional[str] = None,
    source_module: Optional[str] = None,
    include_archived: bool = False,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: NotificationService = Depends(get_notification_service),
):
    handlers = NotificationHandlers(service)
    return await handlers.list_notifications(
        ctx,
        page_token=page_token,
        page_size=page_size,
        status=status,
        type=type,
        severity=severity,
        source_module=source_module,
        include_archived=include_archived,
    )


@router.get("/unread-count", response_model=NotificationUnreadCount)
async def get_unread_count(
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: NotificationService = Depends(get_notification_service),
):
    handlers = NotificationHandlers(service)
    return await handlers.unread_count(ctx)


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: NotificationService = Depends(get_notification_service),
):
    handlers = NotificationHandlers(service)
    return await handlers.get_notification(ctx, notification_id)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: NotificationService = Depends(get_notification_service),
):
    handlers = NotificationHandlers(service)
    return await handlers.mark_read(ctx, notification_id)


@router.post("/read", response_model=NotificationBulkResult)
async def mark_notifications_read(
    request: NotificationReadRequest,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: NotificationService = Depends(get_notification_service),
):
    handlers = NotificationHandlers(service)
    return await handlers.mark_read_bulk(ctx, request)


@router.post("/{notification_id}/archive", response_model=NotificationResponse)
async def archive_notification(
    notification_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: NotificationService = Depends(get_notification_service),
):
    handlers = NotificationHandlers(service)
    return await handlers.archive(ctx, notification_id)
