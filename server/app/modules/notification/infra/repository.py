""" repository

Notification domain repository.
"""

from typing import Optional, List

from sqlalchemy import select, and_, desc, func, update
from sqlalchemy.orm import Session

from app.infra.db.repository import Repository
from app.kernel.contracts.context import RequestContext
from app.modules.notification.domain.models import Notification
from app.kernel.commons.time import utc_now
from app.kernel.contracts.notification import NOTIFICATION_STATUS_READ, NOTIFICATION_STATUS_ARCHIVED


class NotificationRepository(Repository[Notification]):
    """Repository for Notification model."""

    def __init__(self, db: Session, ctx: RequestContext):
        super().__init__(Notification, db, ctx)

    def get_by_id(self, id: str) -> Optional[Notification]:
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
        status: Optional[str] = None,
        type: Optional[str] = None,
        severity: Optional[str] = None,
        source_module: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[Notification]:
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
        if isinstance(result, (list, tuple)):
            return int(result[0])
        if hasattr(result, "_mapping"):
            return int(result[0])
        return int(result)

    def mark_read(self, notification_id: str) -> Optional[Notification]:
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

    def mark_read_bulk(self, ids: List[str]) -> int:
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

    def archive(self, notification_id: str) -> Optional[Notification]:
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
