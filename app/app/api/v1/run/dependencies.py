""" dependencies

Run entry dependencies.
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.infra.db.session import get_db
from app.middleware.auth import get_current_context
from app.kernel.trace.service import RunService
from app.wiring.services import build_run_service


def get_run_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> RunService:
    """Get run service instance."""
    return build_run_service(db=db, ctx=ctx)
