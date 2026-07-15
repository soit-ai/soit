""" service

Notification domain service.
"""


from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apprise import Apprise
from sqlalchemy.orm import Session

from app.kernel.commons.errors import ForbiddenError, NotFoundError, ValidationError
from app.kernel.commons.ids import generate_notification_id, generate_ulid
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.notification import (
    NOTIFICATION_STATUS_UNREAD,
)
from app.kernel.events.envelope import DomainEventEnvelope
from app.kernel.events.outbox_repo import OutboxRepository
from app.kernel.events.publisher import OutboxPublisher
from app.kernel.ports.secrets.interface import SecretsPort
from app.modules.notification.application.schemas import (
    NotificationCreate,
    NotificationEndpointCreate,
    NotificationEndpointUpdate,
    NotificationPreferenceUpdate,
    NotificationReadRequest,
)
from app.modules.notification.domain.models import (
    Notification,
    NotificationDelivery,
    NotificationEndpoint,
    NotificationPreference,
)
from app.modules.notification.infra.repository import NotificationRepository


class NotificationService:
    """Notification service for user inbox."""

    DEFAULT_CATEGORIES = {
        "system": True,
        "security": True,
        "account": True,
        "feature": True,
        "marketing": False,
        "message": True,
        "mention": True,
        "reaction": True,
        "task": True,
        "reminder": True,
        "alert": True,
    }

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        repo: NotificationRepository,
        secrets_port: SecretsPort | None = None,
    ):
        self.db = db
        self.ctx = ctx
        self.repo = repo
        self.secrets_port = secrets_port

    def create_notification(self, data: NotificationCreate) -> Notification:
        target_user_id = data.user_id or self.ctx.user_id
        if target_user_id != self.ctx.user_id and not (
            self.ctx.is_workspace_admin() or self.ctx.is_workspace_owner()
        ):
            raise ForbiddenError("Cannot create notifications for other users")

        now = utc_now()
        notification = Notification(
            id=generate_notification_id(),
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            user_id=target_user_id,
            type=data.type,
            severity=data.severity,
            status=NOTIFICATION_STATUS_UNREAD,
            title=data.title,
            content=data.content,
            source_module=data.source_module,
            action=data.action.model_dump() if data.action else None,
            meta=data.meta,
            created_at=now,
            updated_at=now,
        )
        self.db.add(notification)
        preference = self.repo.get_preference(target_user_id)
        if preference and preference.delivery_mode != "in_app":
            category = (
                "security"
                if data.type == "security" or data.source_module == "security"
                else data.type
            )
            category_enabled = True if category == "security" else preference.categories_json.get(category, True)
            if category_enabled:
                endpoints = self.repo.list_endpoints(target_user_id, active_only=True)
                if preference.delivery_mode == "in_app_email":
                    endpoints = [endpoint for endpoint in endpoints if endpoint.kind == "email"]
                available_at = self._next_delivery_time(preference, now)
                for endpoint in endpoints:
                    self._stage_delivery(notification, endpoint, available_at)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def get_preferences(self) -> NotificationPreference:
        preference = self.repo.get_preference(self.ctx.user_id)
        if preference:
            return preference
        now = utc_now()
        preference = NotificationPreference(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            user_id=self.ctx.user_id,
            delivery_mode="in_app",
            categories_json=dict(self.DEFAULT_CATEGORIES),
            created_at=now,
            updated_at=now,
        )
        self.db.add(preference)
        self.db.commit()
        self.db.refresh(preference)
        return preference

    def update_preferences(self, data: NotificationPreferenceUpdate) -> NotificationPreference:
        try:
            ZoneInfo(data.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValidationError("Unknown notification timezone") from exc
        preference = self.get_preferences()
        categories = {**self.DEFAULT_CATEGORIES, **data.categories}
        categories["security"] = True
        preference.delivery_mode = data.delivery_mode
        preference.categories_json = categories
        preference.quiet_hours_enabled = data.quiet_hours_enabled
        preference.quiet_hours_start = data.quiet_hours_start
        preference.quiet_hours_end = data.quiet_hours_end
        preference.timezone = data.timezone
        preference.updated_at = utc_now()
        self.db.add(preference)
        self.db.commit()
        self.db.refresh(preference)
        return preference

    async def create_endpoint(self, data: NotificationEndpointCreate) -> NotificationEndpoint:
        if self.secrets_port is None:
            raise ValidationError("Notification secrets port is unavailable")
        self._validate_apprise_url(data.url)
        now = utc_now()
        endpoint_id = f"nep_{generate_ulid()}"
        secret_ref = f"secret:notification_endpoint_{endpoint_id}"
        await self.secrets_port.set_secret(secret_ref=secret_ref, value=data.url)
        endpoint = NotificationEndpoint(
            id=endpoint_id,
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            user_id=self.ctx.user_id,
            name=data.name,
            kind=data.kind,
            secret_ref=secret_ref,
            display_target=self._mask_target(data.url),
            status="active",
            created_at=now,
            updated_at=now,
        )
        self.db.add(endpoint)
        self.db.commit()
        self.db.refresh(endpoint)
        return endpoint

    def list_endpoints(self) -> list[NotificationEndpoint]:
        return self.repo.list_endpoints(self.ctx.user_id)

    async def update_endpoint(
        self, endpoint_id: str, data: NotificationEndpointUpdate
    ) -> NotificationEndpoint:
        endpoint = self.repo.get_endpoint(endpoint_id)
        if endpoint is None:
            raise NotFoundError("Notification endpoint not found")
        if data.url is not None:
            if self.secrets_port is None:
                raise ValidationError("Notification secrets port is unavailable")
            self._validate_apprise_url(data.url)
            await self.secrets_port.set_secret(secret_ref=endpoint.secret_ref, value=data.url)
            endpoint.display_target = self._mask_target(data.url)
        if data.name is not None:
            endpoint.name = data.name
        if data.kind is not None:
            endpoint.kind = data.kind
        if data.status is not None:
            endpoint.status = data.status
        endpoint.updated_at = utc_now()
        self.db.add(endpoint)
        self.db.commit()
        self.db.refresh(endpoint)
        return endpoint

    async def delete_endpoint(self, endpoint_id: str) -> None:
        endpoint = self.repo.get_endpoint(endpoint_id)
        if endpoint is None:
            raise NotFoundError("Notification endpoint not found")
        if self.secrets_port is not None:
            await self.secrets_port.delete_secret(secret_ref=endpoint.secret_ref)
        self.db.delete(endpoint)
        self.db.commit()

    def list_deliveries(self, notification_id: str) -> list[NotificationDelivery]:
        self.get_notification(notification_id)
        return self.repo.list_deliveries(notification_id, self.ctx.user_id)

    def test_endpoint(self, endpoint_id: str) -> NotificationDelivery:
        endpoint = self.repo.get_endpoint(endpoint_id)
        if endpoint is None:
            raise NotFoundError("Notification endpoint not found")
        now = utc_now()
        notification = Notification(
            id=generate_notification_id(),
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            user_id=self.ctx.user_id,
            type="system",
            severity="info",
            status=NOTIFICATION_STATUS_UNREAD,
            title="SOIT notification endpoint test",
            content="This is a queued endpoint test notification.",
            source_module="notification",
            created_at=now,
            updated_at=now,
        )
        self.db.add(notification)
        delivery = self._stage_delivery(notification, endpoint, now)
        self.db.commit()
        self.db.refresh(delivery)
        return delivery

    def _stage_delivery(
        self,
        notification: Notification,
        endpoint: NotificationEndpoint,
        available_at: datetime,
    ) -> NotificationDelivery:
        now = utc_now()
        delivery = NotificationDelivery(
            tenant_id=notification.tenant_id,
            workspace_id=notification.workspace_id,
            user_id=notification.user_id,
            notification_id=notification.id,
            endpoint_id=endpoint.id,
            status="queued",
            available_at=available_at,
            created_at=now,
            updated_at=now,
        )
        self.db.add(delivery)
        event_id = f"evt_{generate_ulid()}"
        OutboxPublisher(OutboxRepository(self.db)).publish(
            DomainEventEnvelope(
                event_id=event_id,
                event_type="notification.delivery.requested",
                tenant_id=notification.tenant_id,
                workspace_id=notification.workspace_id,
                idempotency_key=delivery.id,
                subject_type="notification_delivery",
                subject_id=delivery.id,
                producer="notification",
                occurred_at=now,
                payload={"delivery_id": delivery.id},
            ),
            available_at=available_at,
        )
        return delivery

    @staticmethod
    def _validate_apprise_url(url: str) -> None:
        notifier = Apprise()
        if not notifier.add(url):
            raise ValidationError("Invalid Apprise notification URL")

    @staticmethod
    def _mask_target(url: str) -> str:
        scheme, separator, remainder = url.partition("://")
        if not separator:
            return "***"
        if "@" in remainder:
            host = remainder.rsplit("@", 1)[1].split("/", 1)[0]
            return f"{scheme}://***@{host}"
        return f"{scheme}://***"

    @staticmethod
    def _next_delivery_time(preference: NotificationPreference, now: datetime) -> datetime:
        if not preference.quiet_hours_enabled:
            return now
        zone = ZoneInfo(preference.timezone)
        local_now = now.astimezone(zone)
        start = time.fromisoformat(preference.quiet_hours_start)
        end = time.fromisoformat(preference.quiet_hours_end)
        local_time = local_now.time().replace(tzinfo=None)
        in_quiet = start <= local_time < end if start < end else local_time >= start or local_time < end
        if not in_quiet:
            return now
        end_date = local_now.date()
        if start >= end and local_time >= start:
            end_date += timedelta(days=1)
        local_end = datetime.combine(end_date, end, tzinfo=zone)
        return local_end.astimezone(UTC)

    def get_notification(self, notification_id: str) -> Notification:
        notification = self.repo.get_by_id(notification_id)
        if not notification:
            raise NotFoundError("Notification not found")
        return notification

    def list_notifications(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
        type: str | None = None,
        severity: str | None = None,
        source_module: str | None = None,
        include_archived: bool = False,
    ) -> list[Notification]:
        return self.repo.list(
            limit=limit,
            offset=offset,
            status=status,
            type=type,
            severity=severity,
            source_module=source_module,
            include_archived=include_archived,
        )

    def unread_count(self) -> int:
        return self.repo.count_unread()

    def mark_read(self, notification_id: str) -> Notification:
        notification = self.repo.mark_read(notification_id)
        if not notification:
            raise NotFoundError("Notification not found")
        return notification

    def mark_read_bulk(self, request: NotificationReadRequest) -> int:
        if request.all:
            return self.repo.mark_all_read()
        ids = request.ids or []
        return self.repo.mark_read_bulk(ids)

    def archive(self, notification_id: str) -> Notification:
        notification = self.repo.archive(notification_id)
        if not notification:
            raise NotFoundError("Notification not found")
        return notification
