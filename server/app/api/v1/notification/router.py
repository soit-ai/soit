""" router

Notification API routes.
"""


from fastapi import APIRouter, Depends, status

from app.api.v1.notification.dependencies import get_notification_service
from app.api.v1.notification.handlers import NotificationHandlers
from app.api.v1.permissions import (
    require_workspace_read_ctx,
    require_workspace_write_ctx,
)
from app.infra.db.pagination import PaginatedResponse
from app.kernel.contracts.context import RequestContext
from app.modules.notification.application.schemas import (
    NotificationBulkResult,
    NotificationCreate,
    NotificationDeliveryResponse,
    NotificationEndpointCreate,
    NotificationEndpointResponse,
    NotificationEndpointUpdate,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationReadRequest,
    NotificationResponse,
    NotificationUnreadCount,
)
from app.modules.notification.application.service import NotificationService

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
    page_token: str | None = None,
    page_size: int = 20,
    status: str | None = None,
    type: str | None = None,
    severity: str | None = None,
    source_module: str | None = None,
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


@router.get("/preferences", response_model=NotificationPreferenceResponse)
async def get_notification_preferences(
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: NotificationService = Depends(get_notification_service),
):
    return await NotificationHandlers(service).get_preferences(ctx)


@router.put("/preferences", response_model=NotificationPreferenceResponse)
async def update_notification_preferences(
    data: NotificationPreferenceUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: NotificationService = Depends(get_notification_service),
):
    return await NotificationHandlers(service).update_preferences(ctx, data)


@router.get("/endpoints", response_model=list[NotificationEndpointResponse])
async def list_notification_endpoints(
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: NotificationService = Depends(get_notification_service),
):
    return await NotificationHandlers(service).list_endpoints(ctx)


@router.post("/endpoints", response_model=NotificationEndpointResponse, status_code=status.HTTP_201_CREATED)
async def create_notification_endpoint(
    data: NotificationEndpointCreate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: NotificationService = Depends(get_notification_service),
):
    return await NotificationHandlers(service).create_endpoint(ctx, data)


@router.patch("/endpoints/{endpoint_id}", response_model=NotificationEndpointResponse)
async def update_notification_endpoint(
    endpoint_id: str,
    data: NotificationEndpointUpdate,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: NotificationService = Depends(get_notification_service),
):
    return await NotificationHandlers(service).update_endpoint(ctx, endpoint_id, data)


@router.delete("/endpoints/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification_endpoint(
    endpoint_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: NotificationService = Depends(get_notification_service),
):
    await NotificationHandlers(service).delete_endpoint(ctx, endpoint_id)


@router.post(
    "/endpoints/{endpoint_id}/test",
    response_model=NotificationDeliveryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def test_notification_endpoint(
    endpoint_id: str,
    ctx: RequestContext = Depends(require_workspace_write_ctx),
    service: NotificationService = Depends(get_notification_service),
):
    return await NotificationHandlers(service).test_endpoint(ctx, endpoint_id)


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: NotificationService = Depends(get_notification_service),
):
    handlers = NotificationHandlers(service)
    return await handlers.get_notification(ctx, notification_id)


@router.get("/{notification_id}/deliveries", response_model=list[NotificationDeliveryResponse])
async def list_notification_deliveries(
    notification_id: str,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: NotificationService = Depends(get_notification_service),
):
    return await NotificationHandlers(service).list_deliveries(ctx, notification_id)


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
