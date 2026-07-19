""" dependencies

Run entry dependencies.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.infra.db.session import get_db
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.storage.interface import StoragePort
from app.kernel.runtime.runs.service import RunService
from app.middleware.auth import get_current_context
from app.wiring import get_container
from app.wiring.services import build_run_service


def get_run_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> RunService:
    """Get run service instance."""
    return build_run_service(db=db, ctx=ctx)


def get_run_artifact_storage(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
) -> StoragePort:
    """Resolve governed storage for Run artifact content."""

    return get_container().get_storage_port(ctx=ctx)
