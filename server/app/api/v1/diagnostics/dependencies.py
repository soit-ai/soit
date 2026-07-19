"""Diagnostics dependencies."""

from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.storage.interface import StoragePort
from app.middleware.auth import get_current_context
from app.modules.diagnostics.application.service import DiagnosticsService
from app.wiring.container import get_container


def get_diagnostics_storage() -> StoragePort:
    return get_container().get("storage_port")


def get_diagnostics_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StoragePort, Depends(get_diagnostics_storage)],
) -> DiagnosticsService:
    return DiagnosticsService(db=db, ctx=ctx, storage=storage)
