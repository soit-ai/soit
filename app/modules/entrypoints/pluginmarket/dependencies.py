""" dependencies

PluginMarket entry dependencies (ctx/auth/policy).
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.domains.pluginmarket.service import PluginMarketService


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
    return PluginMarketService(db, ctx)


