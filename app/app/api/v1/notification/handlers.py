""" handlers

Notification request handlers.
"""

from typing import Optional

from app.kernel.contracts.context import RequestContext
from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.modules.notification.application.service import NotificationService
from app.modules.notification.application.schemas import (
    NotificationCreate,
    NotificationResponse,
    NotificationReadRequest,
    NotificationUnreadCount,
    NotificationBulkResult,
)


class NotificationHandlers:
    """Handlers for notification API endpoints."""

    def __init__(self, service: NotificationService):
        self.service = service

    async def create_notification(
        self,
        ctx: RequestContext,
        data: NotificationCreate,
    ) -> NotificationResponse:
        notification = self.service.create_notification(data)
        return NotificationResponse.model_validate(notification)

    async def get_notification(
        self,
        ctx: RequestContext,
        notification_id: str,
    ) -> NotificationResponse:
        notification = self.service.get_notification(notification_id)
        return NotificationResponse.model_validate(notification)

    async def list_notifications(
        self,
        ctx: RequestContext,
        page_token: Optional[str] = None,
        page_size: int = 20,
        status: Optional[str] = None,
        type: Optional[str] = None,
        severity: Optional[str] = None,
        source_module: Optional[str] = None,
        include_archived: bool = False,
    ) -> PaginatedResponse[NotificationResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        notifications = self.service.list_notifications(
            limit=limit,
            offset=offset,
            status=status,
            type=type,
            severity=severity,
            source_module=source_module,
            include_archived=include_archived,
        )
        items = [NotificationResponse.model_validate(item) for item in notifications]
        has_next = len(notifications) == limit
        next_offset = offset + len(notifications) if has_next else None
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )

    async def unread_count(self, ctx: RequestContext) -> NotificationUnreadCount:
        count = self.service.unread_count()
        return NotificationUnreadCount(count=count)

    async def mark_read(
        self,
        ctx: RequestContext,
        notification_id: str,
    ) -> NotificationResponse:
        notification = self.service.mark_read(notification_id)
        return NotificationResponse.model_validate(notification)

    async def mark_read_bulk(
        self,
        ctx: RequestContext,
        request: NotificationReadRequest,
    ) -> NotificationBulkResult:
        updated = self.service.mark_read_bulk(request)
        return NotificationBulkResult(updated=updated)

    async def archive(
        self,
        ctx: RequestContext,
        notification_id: str,
    ) -> NotificationResponse:
        notification = self.service.archive(notification_id)
        return NotificationResponse.model_validate(notification)
