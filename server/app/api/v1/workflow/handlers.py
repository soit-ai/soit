""" handlers

Workflow request handlers (thin orchestration).
"""


from fastapi import HTTPException, status

from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.contracts.context import RequestContext
from app.modules.workflow.application.schemas import (
    WorkflowCapabilitiesResponse,
    WorkflowCreate,
    WorkflowDSLExport,
    WorkflowDSLImport,
    WorkflowPublishRequest,
    WorkflowReleaseResponse,
    WorkflowResponse,
    WorkflowRollbackRequest,
    WorkflowTemplateCreate,
    WorkflowUpdate,
    WorkflowVersionCreate,
    WorkflowVersionResponse,
    WorkflowWorkbenchItemsResponse,
    WorkflowWorkbenchResponse,
)
from app.modules.workflow.application.service import WorkflowService


class WorkflowHandlers:
    """Handlers for workflow API endpoints."""

    def __init__(self, service: WorkflowService):
        """Initialize workflow handlers.

        Args:
            service: WorkflowService instance.
        """
        self.service = service

    def _as_version_response(self, version) -> WorkflowVersionResponse:
        """Map WorkflowVersion to WorkflowVersionResponse."""
        return WorkflowVersionResponse(
            id=version.id,
            tenant_id=version.tenant_id,
            workspace_id=version.workspace_id,
            workflow_id=version.workflow_id,
            graph_json=version.spec_json,
            created_by=version.created_by,
            created_at=version.created_at,
        )

    def _as_release_response(self, release) -> WorkflowReleaseResponse:
        """Map WorkflowPublish to WorkflowReleaseResponse."""
        return WorkflowReleaseResponse(
            id=release.id,
            workflow_id=release.workflow_id,
            version_id=release.workflow_version_id,
            action=release.action,
            scope=release.scope,
            status=release.status,
            from_version_id=release.from_version_id,
            to_version_id=release.to_version_id or release.workflow_version_id,
            notes=release.notes,
            rollback_of_publish_id=release.rollback_of_publish_id,
            created_by=release.created_by,
            created_at=release.created_at,
            updated_at=release.updated_at,
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

    async def create_ticket_triage_template(
        self,
        ctx: RequestContext,
        template_in: WorkflowTemplateCreate,
    ) -> WorkflowResponse:
        """Create a ticket triage workflow draft from the built-in template."""
        workflow = await self.service.create_ticket_triage_template(name=template_in.name)
        return WorkflowResponse.model_validate(workflow)

    async def list_workflows(
        self,
        ctx: RequestContext,
        page_token: str | None = None,
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

    async def get_capabilities(self, ctx: RequestContext) -> WorkflowCapabilitiesResponse:
        """Get backend-owned workflow node capabilities."""
        return await self.service.get_capabilities()

    async def get_workbench(
        self,
        ctx: RequestContext,
        page_token: str | None = None,
        page_size: int = 20,
    ) -> WorkflowWorkbenchResponse:
        """Get workflow workbench aggregate data."""
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        return await self.service.get_workbench(limit=limit, offset=offset)

    async def get_workbench_items(
        self,
        ctx: RequestContext,
        page_token: str | None,
        page_size: int,
        tab: str | None,
        keyword: str | None,
    ) -> WorkflowWorkbenchItemsResponse:
        """Get workflow workbench table rows."""
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        return await self.service.get_workbench_items(
            limit=limit,
            offset=offset,
            tab=tab,
            keyword=keyword,
        )

    async def get_workflow(
        self,
        ctx: RequestContext,
        workflow_id: str,
    ) -> WorkflowResponse:
        """Get workflow by ID.

        Args:
            ctx: Request context.
            workflow_id: Workflow ID.

        Returns:
            Workflow details.
        """
        workflow = await self.service.get_workflow(workflow_id)
        return WorkflowResponse.model_validate(workflow)

    async def list_versions(
        self,
        ctx: RequestContext,
        workflow_id: str,
        page_token: str | None = None,
        page_size: int = 20,
    ) -> PaginatedResponse[WorkflowVersionResponse]:
        """List workflow versions.

        Args:
            ctx: Request context.
            workflow_id: Workflow ID.
            page_token: Optional page token.
            page_size: Page size.

        Returns:
            Paginated workflow versions.
        """
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0

        versions = await self.service.list_versions(workflow_id, limit=limit + 1, offset=offset)
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

    async def list_releases(
        self,
        ctx: RequestContext,
        workflow_id: str,
        page_token: str | None = None,
        page_size: int = 20,
    ) -> PaginatedResponse[WorkflowReleaseResponse]:
        """List workflow release ledger entries."""
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0

        releases = await self.service.list_releases(workflow_id, limit=limit + 1, offset=offset)
        has_next = len(releases) > limit
        if has_next:
            releases = releases[:limit]

        items = [self._as_release_response(item) for item in releases]
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
        workflow_id: str,
    ) -> WorkflowVersionResponse:
        """Get current workflow version."""
        version = await self.service.get_current_version(workflow_id)
        if not version:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Current version not found")
        return self._as_version_response(version)

    async def update_workflow(
        self,
        ctx: RequestContext,
        workflow_id: str,
        workflow_in: WorkflowUpdate,
    ) -> WorkflowResponse:
        """Update workflow.

        Args:
            ctx: Request context.
            workflow_id: Workflow ID.
            workflow_in: Workflow update schema.

        Returns:
            Updated workflow.
        """
        workflow = await self.service.update_workflow(workflow_id, workflow_in)
        return WorkflowResponse.model_validate(workflow)

    async def delete_workflow(
        self,
        ctx: RequestContext,
        workflow_id: str,
    ) -> None:
        """Delete workflow.

        Args:
            ctx: Request context.
            workflow_id: Workflow ID.
        """
        await self.service.delete_workflow(workflow_id)

    async def publish_version(
        self,
        ctx: RequestContext,
        workflow_id: str,
        payload: WorkflowPublishRequest,
    ) -> WorkflowResponse:
        """Publish workflow version."""
        workflow = await self.service.publish_version(
            workflow_id,
            payload.version_id,
            run_preflight=payload.preflight,
            notes=payload.notes,
        )
        return WorkflowResponse.model_validate(workflow)

    async def rollback_version(
        self,
        ctx: RequestContext,
        workflow_id: str,
        payload: WorkflowRollbackRequest,
    ) -> WorkflowResponse:
        """Rollback workflow version."""
        workflow = await self.service.rollback_version(
            workflow_id,
            payload.version_id,
            run_preflight=payload.preflight,
            notes=payload.notes,
        )
        return WorkflowResponse.model_validate(workflow)

    async def execute_workflow(
        self,
        ctx: RequestContext,
        workflow_id: str,
        inputs: dict,
    ) -> dict:
        """Execute workflow.

        Args:
            ctx: Request context.
            workflow_id: Workflow ID.
            inputs: Workflow inputs.

        Returns:
            Execution result.
        """
        result = await self.service.execute_workflow(workflow_id, inputs)
        return result

    async def pause_run(
        self,
        ctx: RequestContext,
        workflow_id: str,
        run_id: str,
    ) -> dict:
        """Pause workflow run."""
        return await self.service.pause_run(workflow_id, run_id)

    async def resume_run(
        self,
        ctx: RequestContext,
        workflow_id: str,
        run_id: str,
    ) -> dict:
        """Resume workflow run."""
        return await self.service.resume_run(workflow_id, run_id)

    async def cancel_run(
        self,
        ctx: RequestContext,
        workflow_id: str,
        run_id: str,
        payload: dict | None = None,
    ) -> dict:
        """Cancel workflow run."""
        return await self.service.cancel_run(workflow_id, run_id, reason=(payload or {}).get("reason"))

    async def fail_run(
        self,
        ctx: RequestContext,
        workflow_id: str,
        run_id: str,
        payload: dict | None = None,
    ) -> dict:
        """Mark workflow run failed."""
        data = payload or {}
        return await self.service.fail_run(
            workflow_id,
            run_id,
            error_code=data.get("error_code") or "workflow_run_failed",
            error_message=data.get("error_message"),
        )

    async def retry_run(
        self,
        ctx: RequestContext,
        workflow_id: str,
        run_id: str,
        inputs: dict | None = None,
    ) -> dict:
        """Retry workflow run."""
        return await self.service.retry_run(workflow_id, run_id, inputs)

    async def replay_run(
        self,
        ctx: RequestContext,
        workflow_id: str,
        run_id: str,
        inputs: dict | None = None,
    ) -> dict:
        """Replay workflow run."""
        return await self.service.replay_run(workflow_id, run_id, inputs)

    async def export_dsl(
        self,
        ctx: RequestContext,
        workflow_id: str,
        version_id: str | None = None,
        format: str = "json",
    ) -> WorkflowDSLExport:
        """Export workflow DSL."""
        payload = await self.service.export_dsl(
            workflow_id,
            version_id=version_id,
            format=format,
        )
        return WorkflowDSLExport.model_validate(payload)

    async def import_dsl(
        self,
        ctx: RequestContext,
        workflow_id: str,
        dsl_in: WorkflowDSLImport,
    ) -> WorkflowVersionResponse:
        """Import workflow DSL."""
        version = await self.service.import_dsl(
            workflow_id,
            dsl_in.dsl,
            format=dsl_in.format,
        )
        return self._as_version_response(version)

    async def create_version(
        self,
        ctx: RequestContext,
        workflow_id: str,
        version_in: WorkflowVersionCreate,
    ) -> WorkflowVersionResponse:
        """Create a new workflow version."""
        version = await self.service.create_version(workflow_id, version_in)
        return self._as_version_response(version)
