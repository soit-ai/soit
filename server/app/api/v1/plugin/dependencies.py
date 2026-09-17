"""Plugin entry dependencies."""

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.session import get_async_db
from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.plugin.application.service import PluginService
from app.wiring.services import build_plugin_service


def get_plugin_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> PluginService:
    """Get plugin service instance."""

    return build_plugin_service(db=db, ctx=ctx)
