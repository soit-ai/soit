""" dependencies

AppCenter dependencies.
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.infra.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.appcenter.application.service import AppService
from app.wiring.services import build_appcenter_service


def get_appcenter_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> AppService:
    """Get AppCenter service instance."""
    return build_appcenter_service(db=db, ctx=ctx)
