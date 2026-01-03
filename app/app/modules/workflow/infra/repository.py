""" repository

Workflow repositories.
"""

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.infra.db.repository import Repository
from app.kernel.contracts.context import RequestContext
from app.modules.workflow.domain.models import Workflow, WorkflowVersion


class WorkflowRepository(Repository[Workflow]):
    """Repository for Workflow model."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize workflow repository.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(Workflow, db, ctx)
    
    def get_by_name(self, name: str) -> Optional[Workflow]:
        """Get workflow by name.
        
        Args:
            name: Workflow name.
            
        Returns:
            Workflow instance or None if not found.
        """
        query = select(Workflow).where(
            and_(
                Workflow.tenant_id == self.ctx.tenant_id,
                Workflow.workspace_id == self.ctx.workspace_id,
                Workflow.name == name,
            )
        )
        return self.db.exec(query).first()
    
    def get_current_version(self, workflow_id: str) -> Optional[WorkflowVersion]:
        """Get current version of a workflow.
        
        Args:
            workflow_id: Workflow ID.
            
        Returns:
            WorkflowVersion instance or None if not found.
        """
        workflow = self.get_by_id(workflow_id)
        if not workflow or not workflow.current_version_id:
            return None
        
        return self.db.get(WorkflowVersion, workflow.current_version_id)
    
    def list_versions(
        self,
        workflow_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[WorkflowVersion]:
        """List versions of a workflow.
        
        Args:
            workflow_id: Workflow ID.
            limit: Maximum number of versions to return.
            offset: Offset for pagination.
            
        Returns:
            List of WorkflowVersion instances.
        """
        query = select(WorkflowVersion).where(
            and_(
                WorkflowVersion.tenant_id == self.ctx.tenant_id,
                WorkflowVersion.workspace_id == self.ctx.workspace_id,
                WorkflowVersion.workflow_id == workflow_id,
            )
        ).order_by(WorkflowVersion.created_at.desc()).offset(offset).limit(limit)
        
        return list(self.db.exec(query).all())


class WorkflowVersionRepository(Repository[WorkflowVersion]):
    """Repository for WorkflowVersion model."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize workflow version repository.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        super().__init__(WorkflowVersion, db, ctx)
