""" service

Workflow services (validate, publish, run compile).
"""

from typing import Optional, List
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ValidationError, NotFoundError
from app.modules.domains.workflow.models import Workflow, WorkflowVersion
from app.modules.domains.workflow.repository import WorkflowRepository, WorkflowVersionRepository
from app.modules.domains.workflow.compiler import WorkflowCompiler
from app.modules.domains.workflow.schemas import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowVersionCreate,
)


class WorkflowService:
    """Workflow domain service."""
    
    def __init__(self, db: Session, ctx: RequestContext):
        """Initialize workflow service.
        
        Args:
            db: Database session.
            ctx: Request context.
        """
        self.db = db
        self.ctx = ctx
        self.workflow_repo = WorkflowRepository(db, ctx)
        self.version_repo = WorkflowVersionRepository(db, ctx)
        self.compiler = WorkflowCompiler()
    
    def create_workflow(self, data: WorkflowCreate) -> Workflow:
        """Create a new workflow.
        
        Args:
            data: Workflow creation data.
            
        Returns:
            Created Workflow instance.
            
        Raises:
            ValidationError: If workflow name already exists.
        """
        # Check if name already exists
        existing = self.workflow_repo.get_by_name(data.name)
        if existing:
            raise ValidationError(f"Workflow with name '{data.name}' already exists")
        
        workflow = Workflow(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            name=data.name,
            description=data.description,
        )
        
        return self.workflow_repo.create(workflow)
    
    def update_workflow(self, workflow_id: str, data: WorkflowUpdate) -> Workflow:
        """Update a workflow.
        
        Args:
            workflow_id: Workflow ID.
            data: Workflow update data.
            
        Returns:
            Updated Workflow instance.
            
        Raises:
            NotFoundError: If workflow not found.
            ValidationError: If new name conflicts with existing workflow.
        """
        workflow = self.workflow_repo.get_by_id(workflow_id)
        if not workflow:
            raise NotFoundError(f"Workflow not found: {workflow_id}")
        
        # Check name conflict if name is being changed
        if data.name and data.name != workflow.name:
            existing = self.workflow_repo.get_by_name(data.name)
            if existing and existing.id != workflow_id:
                raise ValidationError(f"Workflow with name '{data.name}' already exists")
            workflow.name = data.name
        
        if data.description is not None:
            workflow.description = data.description
        
        workflow.updated_at = self.workflow_repo.db.query(Workflow).filter(
            Workflow.id == workflow_id
        ).update({"updated_at": self.workflow_repo.db.query(Workflow).filter(
            Workflow.id == workflow_id
        ).first().updated_at})
        
        self.db.commit()
        self.db.refresh(workflow)
        return workflow
    
    def validate_spec(self, graph_json: dict) -> None:
        """Validate WorkflowSpec.
        
        Args:
            graph_json: WorkflowSpec dictionary.
            
        Raises:
            ValidationError: If spec is invalid.
        """
        try:
            validator.validate_workflow_spec(graph_json)
            # Additional validation: try to compile
            self.compiler.compile(graph_json, {}, "dummy_run_id")
        except Exception as e:
            raise ValidationError(f"Invalid workflow spec: {str(e)}")
    
    def publish_version(
        self,
        workflow_id: str,
        data: WorkflowVersionCreate,
    ) -> WorkflowVersion:
        """Publish a new workflow version.
        
        Args:
            workflow_id: Workflow ID.
            data: Version creation data.
            
        Returns:
            Created WorkflowVersion instance.
            
        Raises:
            NotFoundError: If workflow not found.
            ValidationError: If spec is invalid.
        """
        workflow = self.workflow_repo.get_by_id(workflow_id)
        if not workflow:
            raise NotFoundError(f"Workflow not found: {workflow_id}")
        
        # Validate spec
        self.validate_spec(data.graph_json)
        
        # Create version
        version = WorkflowVersion(
            tenant_id=self.ctx.tenant_id,
            workspace_id=self.ctx.workspace_id,
            workflow_id=workflow_id,
            graph_json=data.graph_json,
            created_by=data.created_by,
        )
        
        version = self.version_repo.create(version)
        
        # Update workflow's current_version_id
        from app.kernel.commons.time import utc_now
        workflow.current_version_id = version.id
        workflow.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(workflow)
        
        return version
    
    def get_current_version(self, workflow_id: str) -> Optional[WorkflowVersion]:
        """Get current version of a workflow.
        
        Args:
            workflow_id: Workflow ID.
            
        Returns:
            WorkflowVersion instance or None if no version published.
        """
        return self.workflow_repo.get_current_version(workflow_id)
    
    def list_versions(
        self,
        workflow_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[WorkflowVersion]:
        """List versions of a workflow.
        
        Args:
            workflow_id: Workflow ID.
            limit: Maximum number of versions.
            offset: Offset for pagination.
            
        Returns:
            List of WorkflowVersion instances.
        """
        return self.workflow_repo.list_versions(workflow_id, limit, offset)
    
    def rollback_version(self, workflow_id: str, version_id: str) -> Workflow:
        """Rollback workflow to a specific version.
        
        Args:
            workflow_id: Workflow ID.
            version_id: Version ID to rollback to.
            
        Returns:
            Updated Workflow instance.
            
        Raises:
            NotFoundError: If workflow or version not found.
        """
        workflow = self.workflow_repo.get_by_id(workflow_id)
        if not workflow:
            raise NotFoundError(f"Workflow not found: {workflow_id}")
        
        version = self.version_repo.get_by_id(version_id)
        if not version or version.workflow_id != workflow_id:
            raise NotFoundError(f"Version not found: {version_id}")
        
        from app.kernel.commons.time import utc_now
        workflow.current_version_id = version_id
        workflow.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(workflow)
        
        return workflow
    
    def compile_workflow(
        self,
        workflow_id: str,
        inputs: dict,
        run_id: str,
    ) -> ExecutionPlan:
        """Compile workflow to execution plan.
        
        Args:
            workflow_id: Workflow ID.
            inputs: Workflow inputs.
            run_id: Run ID.
            
        Returns:
            ExecutionPlan instance.
            
        Raises:
            NotFoundError: If workflow or current version not found.
        """
        version = self.get_current_version(workflow_id)
        if not version:
            raise NotFoundError(f"No published version for workflow: {workflow_id}")
        
        return self.compiler.compile(version.graph_json, inputs, run_id)
