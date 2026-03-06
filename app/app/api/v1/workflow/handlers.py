""" handlers

Workflow request handlers (thin orchestration).
"""

from typing import List, Optional
from fastapi import HTTPException, status

from app.kernel.contracts.context import RequestContext
from app.modules.workflow.application.app_facade import WorkflowAppFacadeService
from app.modules.workflow.application.schemas import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowVersionResponse,
    WorkflowVersionCreate,
    WorkflowDSLImport,
    WorkflowDSLExport,
)
from app.infra.db.pagination import PaginatedResponse, parse_page_params, PageToken


class WorkflowHandlers:
    """Handlers for workflow API endpoints."""
    
    def __init__(self, service: WorkflowAppFacadeService):
        """Initialize workflow handlers.
        
        Args:
            service: WorkflowAppFacadeService instance.
        """
        self.service = service

    def _as_version_response(self, version) -> WorkflowVersionResponse:
        """Map AppVersion to WorkflowVersionResponse."""
        return WorkflowVersionResponse(
            id=version.id,
            tenant_id=version.tenant_id,
            workspace_id=version.workspace_id,
            workflow_id=version.app_id,
            graph_json=version.spec_json,
            created_by=version.created_by,
            created_at=version.created_at,
        )
    
    async def create_workflow(
        self,
        ctx: RequestContext,
        workflow_in: WorkflowCreate,
    ) -> WorkflowResponse:
        """Create a new workflow.
        
        Args:
            ctx: Request context.
            workflow_in: Workflow creation schema.
            
        Returns:
            Created workflow.
        """
        workflow = await self.service.create_workflow(workflow_in)
        return WorkflowResponse.model_validate(workflow)
    
    async def list_workflows(
        self,
        ctx: RequestContext,
        page_token: Optional[str] = None,
        page_size: int = 20,
    ) -> PaginatedResponse[WorkflowResponse]:
        """List workflows.
        
        Args:
            ctx: Request context.
            page_token: Optional page token.
            page_size: Page size.
            
        Returns:
            Paginated workflows.
        """
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        
        workflows = await self.service.list_workflows(limit=limit + 1, offset=offset)  # Fetch one extra to check has_next
        
        # Check if there are more workflows
        has_next = len(workflows) > limit
        if has_next:
            workflows = workflows[:limit]  # Remove the extra item
        
        # Convert items to WorkflowResponse
        items = [WorkflowResponse.model_validate(wf) for wf in workflows]
        
        next_offset = offset + len(items) if has_next else None
        
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )
    
    async def get_workflow(
        self,
        ctx: RequestContext,
        app_id: str,
    ) -> WorkflowResponse:
        """Get workflow by ID.
        
        Args:
            ctx: Request context.
            app_id: App ID.
            
        Returns:
            Workflow details.
        """
        workflow = await self.service.get_workflow(app_id)
        return WorkflowResponse.model_validate(workflow)

    async def list_versions(
        self,
        ctx: RequestContext,
        app_id: str,
        page_token: Optional[str] = None,
        page_size: int = 20,
    ) -> PaginatedResponse[WorkflowVersionResponse]:
        """List workflow versions.

        Args:
            ctx: Request context.
            app_id: App ID.
            page_token: Optional page token.
            page_size: Page size.

        Returns:
            Paginated workflow versions.
        """
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0

        versions = await self.service.list_versions(app_id, limit=limit + 1, offset=offset)
        has_next = len(versions) > limit
        if has_next:
            versions = versions[:limit]

        items = [self._as_version_response(item) for item in versions]
        next_offset = offset + len(items) if has_next else None

        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )

    async def get_current_version(
        self,
        ctx: RequestContext,
        app_id: str,
    ) -> WorkflowVersionResponse:
        """Get current workflow version."""
        version = await self.service.get_current_version(app_id)
        if not version:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current version not found")
        return self._as_version_response(version)
    
    async def update_workflow(
        self,
        ctx: RequestContext,
        app_id: str,
        workflow_in: WorkflowUpdate,
    ) -> WorkflowResponse:
        """Update workflow.
        
        Args:
            ctx: Request context.
            app_id: App ID.
            workflow_in: Workflow update schema.
            
        Returns:
            Updated workflow.
        """
        workflow = await self.service.update_workflow(app_id, workflow_in)
        return WorkflowResponse.model_validate(workflow)
    
    async def delete_workflow(
        self,
        ctx: RequestContext,
        app_id: str,
    ) -> None:
        """Delete workflow.
        
        Args:
            ctx: Request context.
            app_id: App ID.
        """
        await self.service.delete_workflow(app_id)
    
    async def publish_version(
        self,
        ctx: RequestContext,
        app_id: str,
        version_id: str,
        preflight: bool = False,
    ) -> WorkflowResponse:
        """Publish workflow version.
        
        Args:
            ctx: Request context.
            app_id: App ID.
            version_id: Version ID.
            
        Returns:
            Updated workflow.
        """
        # Rollback to specific version (which publishes it)
        workflow = await self.service.rollback_version(app_id, version_id, run_preflight=preflight)
        return WorkflowResponse.model_validate(workflow)
    
    async def execute_workflow(
        self,
        ctx: RequestContext,
        app_id: str,
        inputs: dict,
    ) -> dict:
        """Execute workflow.
        
        Args:
            ctx: Request context.
            app_id: App ID.
            inputs: Workflow inputs.
            
        Returns:
            Execution result.
        """
        result = await self.service.execute_workflow(app_id, inputs)
        return result

    async def pause_run(
        self,
        ctx: RequestContext,
        app_id: str,
        run_id: str,
    ) -> dict:
        """Pause workflow run."""
        return await self.service.pause_run(app_id, run_id)

    async def resume_run(
        self,
        ctx: RequestContext,
        app_id: str,
        run_id: str,
    ) -> dict:
        """Resume workflow run."""
        return await self.service.resume_run(app_id, run_id)

    async def retry_run(
        self,
        ctx: RequestContext,
        app_id: str,
        run_id: str,
        inputs: Optional[dict] = None,
    ) -> dict:
        """Retry workflow run."""
        return await self.service.retry_run(app_id, run_id, inputs)

    async def replay_run(
        self,
        ctx: RequestContext,
        app_id: str,
        run_id: str,
        inputs: Optional[dict] = None,
    ) -> dict:
        """Replay workflow run."""
        return await self.service.replay_run(app_id, run_id, inputs)

    async def export_dsl(
        self,
        ctx: RequestContext,
        app_id: str,
        version_id: Optional[str] = None,
        format: str = "json",
    ) -> WorkflowDSLExport:
        """Export workflow DSL."""
        payload = await self.service.export_dsl(
            app_id,
            version_id=version_id,
            format=format,
        )
        return WorkflowDSLExport.model_validate(payload)

    async def import_dsl(
        self,
        ctx: RequestContext,
        app_id: str,
        dsl_in: WorkflowDSLImport,
    ) -> WorkflowVersionResponse:
        """Import workflow DSL."""
        version = await self.service.import_dsl(
            app_id,
            dsl_in.dsl,
            dsl_in.created_by,
            format=dsl_in.format,
        )
        return self._as_version_response(version)

    async def create_version(
        self,
        ctx: RequestContext,
        app_id: str,
        version_in: WorkflowVersionCreate,
    ) -> WorkflowVersionResponse:
        """Create a new workflow version."""
        version = await self.service.publish_version(app_id, version_in)
        return self._as_version_response(version)
