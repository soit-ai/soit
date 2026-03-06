""" dependencies

Bot entry dependencies.
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.infra.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.bot.application.app_facade import BotAppFacadeService
from app.wiring.services import build_bot_service


def get_bot_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> BotAppFacadeService:
    """Get bot service instance."""
    return build_bot_service(db=db, ctx=ctx)
