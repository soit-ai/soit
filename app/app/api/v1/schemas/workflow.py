""" workflow

Workflow response serializers.
"""

from typing import Optional, Dict, Any
from datetime import datetime

from app.modules.workflow.domain.models import Workflow, WorkflowVersion
from app.modules.workflow.application.schemas import WorkflowResponse, WorkflowVersionResponse


def serialize_workflow(workflow: Workflow) -> Dict[str, Any]:
    """Serialize workflow model to dictionary.
    
    Args:
        workflow: Workflow model instance.
        
    Returns:
        Serialized workflow dictionary.
    """
    return WorkflowResponse.model_validate(workflow).model_dump()


def serialize_workflow_version(version: WorkflowVersion) -> Dict[str, Any]:
    """Serialize workflow version model to dictionary.
    
    Args:
        version: WorkflowVersion model instance.
        
    Returns:
        Serialized version dictionary.
    """
    return WorkflowVersionResponse.model_validate(version).model_dump()

