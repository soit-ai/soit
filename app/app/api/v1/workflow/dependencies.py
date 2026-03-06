""" dependencies

Workflow entry dependencies (ctx/auth/policy).
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.infra.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.workflow.application.app_facade import WorkflowAppFacadeService
from app.wiring.services import build_workflow_service


def get_workflow_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkflowAppFacadeService:
    """Get workflow service instance."""
    return build_workflow_service(db=db, ctx=ctx)
