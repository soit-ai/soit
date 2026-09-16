"""Billing API dependencies."""

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.session import get_async_db
from app.kernel.contracts.context import RequestContext
from app.middleware.auth import get_current_context
from app.modules.billing.application.service import CreditService


def get_credit_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> CreditService:
    """Get workspace-scoped credit service."""
    return CreditService(db=db, ctx=ctx)
