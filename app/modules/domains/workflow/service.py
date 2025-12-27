""" service

Workflow services (validate, publish, run compile).
"""

from typing import Optional, List
from sqlalchemy.orm import Session

from typing import Dict, Any
from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ValidationError, NotFoundError
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.modules.domains.workflow.models import Workflow, WorkflowVersion
from app.modules.domains.workflow.repository import WorkflowRepository, WorkflowVersionRepository
from app.modules.domains.workflow.compiler import WorkflowCompiler
from app.modules.domains.workflow.schemas import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowVersionCreate,
)
from app.kernel.specs.validator import validator


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
        
        plan = self.compiler.compile(version.graph_json, inputs, run_id)
        # Set app_version_id to workflow_id for trace tracking
        plan.app_version_id = workflow_id
        return plan
    
    async def execute_workflow(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a workflow.
        
        Args:
            workflow_id: Workflow ID.
            inputs: Workflow inputs.
            
        Returns:
            Execution result.
            
        Raises:
            NotFoundError: If workflow or current version not found.
        """
        from app.kernel.commons.ids import generate_ulid
        from app.kernel.execution.engine import ExecutionEngine
        from app.kernel.trace.writer import TraceWriter
        
        # Generate run ID
        run_id = generate_ulid()
        
        # Compile workflow to execution plan
        plan = self.compile_workflow(workflow_id, inputs, run_id)
        
        # Initialize execution engine
        trace_writer = TraceWriter(self.db, self.ctx)
        execution_engine = ExecutionEngine(
            db=self.db,
            ctx=self.ctx,
            trace_writer=trace_writer,
        )
        
        # Execute workflow
        result = await execution_engine.execute(plan)
        
        return result
    
    def get_workflow(self, workflow_id: str) -> Workflow:
        """Get workflow by ID.
        
        Args:
            workflow_id: Workflow ID.
            
        Returns:
            Workflow instance.
            
        Raises:
            NotFoundError: If workflow not found.
        """
        workflow = self.workflow_repo.get_by_id(workflow_id)
        if not workflow:
            raise NotFoundError(f"Workflow not found: {workflow_id}")
        return workflow
    
    def list_workflows(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Workflow]:
        """List workflows.
        
        Args:
            limit: Maximum number of workflows.
            offset: Offset for pagination.
            
        Returns:
            List of Workflow instances.
        """
        from sqlalchemy import select, and_, desc
        from app.modules.domains.workflow.models import Workflow
        
        query = select(Workflow).where(
            and_(
                Workflow.tenant_id == self.ctx.tenant_id,
                Workflow.workspace_id == self.ctx.workspace_id,
            )
        ).order_by(desc(Workflow.created_at)).offset(offset).limit(limit)
        
        return list(self.db.exec(query).all())
    
    def delete_workflow(self, workflow_id: str) -> None:
        """Delete a workflow (soft delete).
        
        Args:
            workflow_id: Workflow ID.
            
        Raises:
            NotFoundError: If workflow not found.
        """
        workflow = self.get_workflow(workflow_id)
        
        # Soft delete
        from app.kernel.commons.time import utc_now
        workflow.deleted_at = utc_now()
        workflow.updated_at = utc_now()
        
        self.db.commit()
    
    def list_runs(
        self,
        workflow_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[dict]:
        """List runs for a workflow.
        
        Args:
            workflow_id: Workflow ID.
            limit: Maximum number of runs.
            offset: Offset for pagination.
            
        Returns:
            List of run dictionaries.
        """
        from app.kernel.trace.models import Run
        from sqlalchemy import select, and_, desc
        
        # Query runs for this workflow
        # Using app_version_id to store workflow_id (as per ExecutionPlan contract)
        # The composite index ix_runs_tenant_workspace_app_version_mode_created optimizes this query
        query = select(Run).where(
            and_(
                Run.tenant_id == self.ctx.tenant_id,
                Run.workspace_id == self.ctx.workspace_id,
                Run.app_version_id == workflow_id,  # workflow_id is stored in app_version_id
                Run.mode == "workflow",  # Filter by mode to ensure it's a workflow run
            )
        ).order_by(desc(Run.created_at)).offset(offset).limit(limit)
        
        runs = list(self.db.exec(query).all())
        
        # Convert to dictionaries
        result = []
        for run in runs:
            result.append({
                "id": run.id,
                "workflow_id": workflow_id,
                "status": run.status,
                "mode": run.mode,
                "input_summary": run.input_summary,
                "output_summary": run.output_summary,
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            })
        
        return result
    
    def get_run(self, workflow_id: str, run_id: str) -> dict:
        """Get run details.
        
        Args:
            workflow_id: Workflow ID.
            run_id: Run ID.
            
        Returns:
            Run details dictionary.
            
        Raises:
            NotFoundError: If run not found.
        """
        from app.kernel.trace.models import Run, RunStep, RunArtifact, RunCost
        from sqlalchemy import select, and_
        
        # Get run
        query = select(Run).where(
            and_(
                Run.id == run_id,
                Run.tenant_id == self.ctx.tenant_id,
                Run.workspace_id == self.ctx.workspace_id,
                Run.app_version_id == workflow_id,  # workflow_id is stored in app_version_id
                Run.mode == "workflow",  # Filter by mode to ensure it's a workflow run
            )
        )
        run = self.db.exec(query).first()
        
        if not run:
            raise NotFoundError(f"Run not found: {run_id}")
        
        # Get steps
        steps_query = select(RunStep).where(
            and_(
                RunStep.run_id == run_id,
                RunStep.tenant_id == self.ctx.tenant_id,
                RunStep.workspace_id == self.ctx.workspace_id,
            )
        ).order_by(RunStep.created_at)
        steps = list(self.db.exec(steps_query).all())
        
        # Get artifacts
        artifacts_query = select(RunArtifact).where(
            and_(
                RunArtifact.run_id == run_id,
                RunArtifact.tenant_id == self.ctx.tenant_id,
                RunArtifact.workspace_id == self.ctx.workspace_id,
            )
        )
        artifacts = list(self.db.exec(artifacts_query).all())
        
        # Get costs
        costs_query = select(RunCost).where(
            and_(
                RunCost.run_id == run_id,
                RunCost.tenant_id == self.ctx.tenant_id,
                RunCost.workspace_id == self.ctx.workspace_id,
            )
        )
        costs = list(self.db.exec(costs_query).all())
        
        # Build result
        result = {
            "id": run.id,
            "workflow_id": workflow_id,
            "status": run.status,
            "mode": run.mode,
            "input_summary": run.input_summary,
            "output_summary": run.output_summary,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            "steps": [
                {
                    "id": step.id,
                    "step_id": step.step_id,
                    "status": step.status,
                    "input_summary": step.input_summary,
                    "output_summary": step.output_summary,
                    "created_at": step.created_at.isoformat() if step.created_at else None,
                    "updated_at": step.updated_at.isoformat() if step.updated_at else None,
                }
                for step in steps
            ],
            "artifacts": [
                {
                    "id": artifact.id,
                    "artifact_key": artifact.artifact_key,
                    "artifact_type": artifact.artifact_type,
                    "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
                }
                for artifact in artifacts
            ],
            "costs": [
                {
                    "id": cost.id,
                    "provider": cost.provider,
                    "model": cost.model,
                    "input_tokens": cost.input_tokens,
                    "output_tokens": cost.output_tokens,
                    "cost_usd": float(cost.cost_usd) if cost.cost_usd else None,
                    "created_at": cost.created_at.isoformat() if cost.created_at else None,
                }
                for cost in costs
            ],
        }
        
        return result
