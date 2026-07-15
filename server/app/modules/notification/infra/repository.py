""" repository

Notification domain repository.
"""

from __future__ import annotations

import builtins

from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.orm import Session

from app.infra.db.repository import Repository
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.notification import (
    NOTIFICATION_STATUS_ARCHIVED,
    NOTIFICATION_STATUS_READ,
)
from app.modules.notification.domain.models import (
    Notification,
    NotificationDelivery,
    NotificationEndpoint,
    NotificationPreference,
)


class NotificationRepository(Repository[Notification]):
    """Repository for Notification model."""

    def __init__(self, db: Session, ctx: RequestContext):
        super().__init__(Notification, db, ctx)

    def get_by_id(self, id: str) -> Notification | None:
        query = select(Notification).where(
            and_(
                Notification.id == id,
                Notification.user_id == self.ctx.user_id,
            )
        )
        query = self._apply_scope(query)
        result = self.db.exec(query).first()
        return self._unwrap_result(result)

    def list(
        self,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
        type: str | None = None,
        severity: str | None = None,
        source_module: str | None = None,
        include_archived: bool = False,
    ) -> list[Notification]:
        query = select(Notification).where(
            and_(
                Notification.user_id == self.ctx.user_id,
            )
        )
        query = self._apply_scope(query)

        if status:
            query = query.where(Notification.status == status)
        elif not include_archived:
            query = query.where(Notification.status != NOTIFICATION_STATUS_ARCHIVED)

        if type:
            query = query.where(Notification.type == type)
        if severity:
            query = query.where(Notification.severity == severity)
        if source_module:
            query = query.where(Notification.source_module == source_module)

        query = query.order_by(desc(Notification.created_at)).offset(offset).limit(limit)
        results = list(self.db.exec(query).all())
        return self._unwrap_all(results)

    def count_unread(self) -> int:
        query = select(func.count()).select_from(Notification).where(
            and_(
                Notification.user_id == self.ctx.user_id,
                Notification.status != NOTIFICATION_STATUS_ARCHIVED,
                Notification.status != NOTIFICATION_STATUS_READ,
            )
        )
        query = self._apply_scope(query)
        result = self.db.exec(query).one()
        if isinstance(result, list | tuple):
            return int(result[0])
        if hasattr(result, "_mapping"):
            return int(result[0])
        return int(result)

    def mark_read(self, notification_id: str) -> Notification | None:
        notification = self.get_by_id(notification_id)
        if not notification:
            return None
        if notification.status != NOTIFICATION_STATUS_READ:
            now = utc_now()
            notification.status = NOTIFICATION_STATUS_READ
            notification.read_at = now
            notification.updated_at = now
            self.db.add(notification)
            self.db.commit()
            self.db.refresh(notification)
        return notification

    def mark_read_bulk(self, ids: builtins.list[str]) -> int:
        if not ids:
            return 0
        now = utc_now()
        stmt = (
            update(Notification)
            .where(
                and_(
                    Notification.id.in_(ids),
                    Notification.user_id == self.ctx.user_id,
                    Notification.status != NOTIFICATION_STATUS_ARCHIVED,
                )
            )
            .values(status=NOTIFICATION_STATUS_READ, read_at=now, updated_at=now)
        )
        stmt = self._apply_scope(stmt)
        result = self.db.exec(stmt)
        self.db.commit()
        return result.rowcount or 0

    def mark_all_read(self) -> int:
        now = utc_now()
        stmt = (
            update(Notification)
            .where(
                and_(
                    Notification.user_id == self.ctx.user_id,
                    Notification.status != NOTIFICATION_STATUS_READ,
                    Notification.status != NOTIFICATION_STATUS_ARCHIVED,
                )
            )
            .values(status=NOTIFICATION_STATUS_READ, read_at=now, updated_at=now)
        )
        stmt = self._apply_scope(stmt)
        result = self.db.exec(stmt)
        self.db.commit()
        return result.rowcount or 0

    def archive(self, notification_id: str) -> Notification | None:
        notification = self.get_by_id(notification_id)
        if not notification:
            return None
        if notification.status != NOTIFICATION_STATUS_ARCHIVED:
            now = utc_now()
            notification.status = NOTIFICATION_STATUS_ARCHIVED
            notification.archived_at = now
            notification.updated_at = now
            self.db.add(notification)
            self.db.commit()
            self.db.refresh(notification)
        return notification

    def get_preference(self, user_id: str) -> NotificationPreference | None:
        query = select(NotificationPreference).where(
            and_(
                NotificationPreference.tenant_id == self.ctx.tenant_id,
                NotificationPreference.workspace_id == self.ctx.workspace_id,
                NotificationPreference.user_id == user_id,
            )
        )
        result = self.db.exec(query).first()
        if isinstance(result, NotificationPreference):
            return result
        if isinstance(result, tuple) or hasattr(result, "_mapping"):
            return result[0]
        return result

    def list_endpoints(
        self, user_id: str, *, active_only: bool = False
    ) -> builtins.list[NotificationEndpoint]:
        query = select(NotificationEndpoint).where(
            and_(
                NotificationEndpoint.tenant_id == self.ctx.tenant_id,
                NotificationEndpoint.workspace_id == self.ctx.workspace_id,
                NotificationEndpoint.user_id == user_id,
            )
        )
        if active_only:
            query = query.where(NotificationEndpoint.status == "active")
        results = list(self.db.exec(query.order_by(desc(NotificationEndpoint.created_at))).all())
        return [item if isinstance(item, NotificationEndpoint) else item[0] for item in results]

    def get_endpoint(self, endpoint_id: str, user_id: str | None = None) -> NotificationEndpoint | None:
        query = select(NotificationEndpoint).where(
            and_(
                NotificationEndpoint.id == endpoint_id,
                NotificationEndpoint.tenant_id == self.ctx.tenant_id,
                NotificationEndpoint.workspace_id == self.ctx.workspace_id,
                NotificationEndpoint.user_id == (user_id or self.ctx.user_id),
            )
        )
        result = self.db.exec(query).first()
        if result is None or isinstance(result, NotificationEndpoint):
            return result
        return result[0]

    def list_deliveries(
        self, notification_id: str, user_id: str
    ) -> builtins.list[NotificationDelivery]:
        query = select(NotificationDelivery).where(
            and_(
                NotificationDelivery.tenant_id == self.ctx.tenant_id,
                NotificationDelivery.workspace_id == self.ctx.workspace_id,
                NotificationDelivery.user_id == user_id,
                NotificationDelivery.notification_id == notification_id,
            )
        )
        results = list(self.db.exec(query.order_by(desc(NotificationDelivery.created_at))).all())
        return [item if isinstance(item, NotificationDelivery) else item[0] for item in results]
