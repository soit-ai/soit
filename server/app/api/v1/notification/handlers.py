""" handlers

Notification request handlers.
"""


from app.infra.db.pagination import PaginatedResponse, parse_page_params
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


class NotificationHandlers:
    """Handlers for notification API endpoints."""

    def __init__(self, service: NotificationService):
        self.service = service

    @staticmethod
    def _preference_response(preference) -> NotificationPreferenceResponse:
        return NotificationPreferenceResponse.model_validate(
            {
                "id": preference.id,
                "delivery_mode": preference.delivery_mode,
                "categories": preference.categories_json,
                "quiet_hours_enabled": preference.quiet_hours_enabled,
                "quiet_hours_start": preference.quiet_hours_start,
                "quiet_hours_end": preference.quiet_hours_end,
                "timezone": preference.timezone,
                "created_at": preference.created_at,
                "updated_at": preference.updated_at,
            }
        )

    async def get_preferences(self, ctx: RequestContext) -> NotificationPreferenceResponse:
        return self._preference_response(self.service.get_preferences())

    async def update_preferences(
        self, ctx: RequestContext, data: NotificationPreferenceUpdate
    ) -> NotificationPreferenceResponse:
        return self._preference_response(self.service.update_preferences(data))

    async def list_endpoints(self, ctx: RequestContext) -> list[NotificationEndpointResponse]:
        return [NotificationEndpointResponse.model_validate(item) for item in self.service.list_endpoints()]

    async def create_endpoint(
        self, ctx: RequestContext, data: NotificationEndpointCreate
    ) -> NotificationEndpointResponse:
        return NotificationEndpointResponse.model_validate(await self.service.create_endpoint(data))

    async def update_endpoint(
        self, ctx: RequestContext, endpoint_id: str, data: NotificationEndpointUpdate
    ) -> NotificationEndpointResponse:
        return NotificationEndpointResponse.model_validate(
            await self.service.update_endpoint(endpoint_id, data)
        )

    async def delete_endpoint(self, ctx: RequestContext, endpoint_id: str) -> None:
        await self.service.delete_endpoint(endpoint_id)

    async def test_endpoint(
        self, ctx: RequestContext, endpoint_id: str
    ) -> NotificationDeliveryResponse:
        return NotificationDeliveryResponse.model_validate(self.service.test_endpoint(endpoint_id))

    async def list_deliveries(
        self, ctx: RequestContext, notification_id: str
    ) -> list[NotificationDeliveryResponse]:
        return [
            NotificationDeliveryResponse.model_validate(item)
            for item in self.service.list_deliveries(notification_id)
        ]

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
        page_token: str | None = None,
        page_size: int = 20,
        status: str | None = None,
        type: str | None = None,
        severity: str | None = None,
        source_module: str | None = None,
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
