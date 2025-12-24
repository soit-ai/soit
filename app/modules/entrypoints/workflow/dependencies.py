""" dependencies

Workflow entry dependencies (ctx/auth/policy).
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.domains.workflow.service import WorkflowService


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
    return WorkflowService(db, ctx)

