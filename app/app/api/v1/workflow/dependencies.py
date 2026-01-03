""" dependencies

Workflow entry dependencies (ctx/auth/policy).
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.infra.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.workflow.application.service import WorkflowService
from app.modules.workflow.infra.repository import WorkflowRepository, WorkflowVersionRepository



def get_workflow_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    db: Annotated[Session, Depends(get_db)],
) -> WorkflowService:
    """Get workflow service instance.
    
    Args:
        ctx: Request context.
        db: Database session.
        
    Returns:
        WorkflowService instance.
    """
    workflow_repo = WorkflowRepository(db, ctx)
    version_repo = WorkflowVersionRepository(db, ctx)
    return WorkflowService(db, ctx, workflow_repo, version_repo)

