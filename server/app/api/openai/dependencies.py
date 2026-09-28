"""Dependencies of the OpenAI-compatible entry point."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.session import get_async_db
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.catalog import ModelCatalogPort
from app.middleware.auth import get_current_context
from app.wiring.model_catalog import ModelHubCatalog


def get_model_catalog(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> ModelCatalogPort:
    return ModelHubCatalog(db=db, ctx=ctx)
