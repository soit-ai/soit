""" dependencies

Dataset entry dependencies (ctx/auth/policy).
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.infra.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.dataset.application.service import DatasetService
from app.wiring.services import build_dataset_service


def get_dataset_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> DatasetService:
    """Get dataset service instance."""
    return build_dataset_service(db=db, ctx=ctx)
