""" dependencies

Notification entry dependencies.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.notification.application.service import NotificationService
from app.wiring.services import build_notification_service


def get_notification_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> NotificationService:
    """Get notification service instance."""
    return build_notification_service(db=db, ctx=ctx)
