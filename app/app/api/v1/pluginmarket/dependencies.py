""" dependencies

PluginMarket entry dependencies (ctx/auth/policy).
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.infra.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.pluginmarket.application.service import PluginMarketService
from app.modules.pluginmarket.infra.repository import PluginRepository, PluginInstallationRepository



def get_pluginmarket_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> PluginMarketService:
    """Get plugin market service instance.
    
    Args:
        ctx: Request context.
        db: Database session.
        
    Returns:
        PluginMarketService instance.
    """
    plugin_repo = PluginRepository(db, ctx)
    installation_repo = PluginInstallationRepository(db, ctx)
    return PluginMarketService(db, ctx, plugin_repo, installation_repo)


