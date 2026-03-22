""" service

Notification domain service.
"""

from typing import Optional, List

from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.ids import generate_notification_id
from app.kernel.commons.time import utc_now
from app.kernel.commons.errors import NotFoundError, ForbiddenError
from app.kernel.contracts.notification import (
    NOTIFICATION_STATUS_UNREAD,
)
from app.modules.notification.domain.models import Notification
from app.modules.notification.infra.repository import NotificationRepository
from app.modules.notification.application.schemas import (
    NotificationCreate,
    NotificationReadRequest,
)


class NotificationService:
    """Notification service for user inbox."""

    def __init__(self, db: Session, ctx: RequestContext, repo: NotificationRepository):
        self.db = db
        self.ctx = ctx
        self.repo = repo

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
        return self.repo.create(notification)

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
        status: Optional[str] = None,
        type: Optional[str] = None,
        severity: Optional[str] = None,
        source_module: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[Notification]:
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
