""" dependencies

Chat entry dependencies (ctx/auth/policy).
"""

from typing import Annotated
from fastapi import Depends
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.db.session import get_db
from app.middleware.auth import get_current_context
from app.modules.domains.workflow.service import WorkflowService
from app.modules.entrypoints.workflow.dependencies import get_workflow_service


def get_chat_service(
    ctx: Annotated[RequestContext, Depends(get_current_context)],
    workflow_service: WorkflowService = Depends(get_workflow_service),
) -> "ChatService":
    """Get chat service instance.
    
    Args:
        ctx: Request context.
        workflow_service: WorkflowService instance for executing workflows.
        
    Returns:
        ChatService instance.
    """
    # Chat service uses workflow service for execution
    # In the future, this could be a dedicated ChatService
    return workflow_service
