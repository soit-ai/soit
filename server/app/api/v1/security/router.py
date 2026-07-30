""" router

Security API routes (FastAPI).
"""


from fastapi import APIRouter, Depends

from app.api.v1.permissions import (
    require_tenant_admin_ctx,
    require_workspace_governance_ctx,
    require_workspace_read_ctx,
)
from app.api.v1.security.dependencies import get_security_service
from app.api.v1.security.handlers import SecurityHandlers
from app.infra.db.pagination import PaginatedResponse
from app.kernel.contracts.context import RequestContext
from app.modules.security.application.schemas import (
    EgressPolicyAuditResponse,
    EgressPolicyResponse,
    EgressPolicyUpdate,
    UsagePolicyResponse,
    UsagePolicyUpdate,
)
from app.modules.security.application.service import SecurityService

router = APIRouter()


@router.get("/egress/tenant", response_model=EgressPolicyResponse)
async def get_tenant_policy(
    ctx: RequestContext = Depends(require_tenant_admin_ctx),
    service: SecurityService = Depends(get_security_service),
):
    """Get tenant-level egress policy."""
    handlers = SecurityHandlers(service)
    return await handlers.get_tenant_policy(ctx)


@router.put("/egress/tenant", response_model=EgressPolicyResponse)
async def update_tenant_policy(
    data: EgressPolicyUpdate,
    ctx: RequestContext = Depends(require_tenant_admin_ctx),
    service: SecurityService = Depends(get_security_service),
):
    """Update tenant-level egress policy."""
    handlers = SecurityHandlers(service)
    return await handlers.update_tenant_policy(ctx, data)


@router.get("/egress/workspace", response_model=EgressPolicyResponse)
async def get_workspace_policy(
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: SecurityService = Depends(get_security_service),
):
    """Get workspace-level egress policy."""
    handlers = SecurityHandlers(service)
    return await handlers.get_workspace_policy(ctx)


@router.put("/egress/workspace", response_model=EgressPolicyResponse)
async def update_workspace_policy(
    data: EgressPolicyUpdate,
    ctx: RequestContext = Depends(require_workspace_governance_ctx),
    service: SecurityService = Depends(get_security_service),
):
    """Update workspace-level egress policy."""
    handlers = SecurityHandlers(service)
    return await handlers.update_workspace_policy(ctx, data)


@router.get("/egress/audits", response_model=PaginatedResponse[EgressPolicyAuditResponse])
async def list_egress_audits(
    scope: str | None = None,
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: SecurityService = Depends(get_security_service),
):
    """List egress policy audits."""
    handlers = SecurityHandlers(service)
    return await handlers.list_audits(ctx, scope, page_token, page_size)


@router.get("/limits/tenant", response_model=UsagePolicyResponse)
async def get_tenant_limits(
    ctx: RequestContext = Depends(require_tenant_admin_ctx),
    service: SecurityService = Depends(get_security_service),
):
    """Get tenant-level rate limits and quotas."""
    handlers = SecurityHandlers(service)
    return await handlers.get_tenant_usage_policy(ctx)


@router.put("/limits/tenant", response_model=UsagePolicyResponse)
async def update_tenant_limits(
    data: UsagePolicyUpdate,
    ctx: RequestContext = Depends(require_tenant_admin_ctx),
    service: SecurityService = Depends(get_security_service),
):
    """Update tenant-level rate limits and quotas."""
    handlers = SecurityHandlers(service)
    return await handlers.update_tenant_usage_policy(ctx, data)


@router.get("/limits/workspace", response_model=UsagePolicyResponse)
async def get_workspace_limits(
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: SecurityService = Depends(get_security_service),
):
    """Get workspace-level rate limits and quotas."""
    handlers = SecurityHandlers(service)
    return await handlers.get_workspace_usage_policy(ctx)


@router.put("/limits/workspace", response_model=UsagePolicyResponse)
async def update_workspace_limits(
    data: UsagePolicyUpdate,
    ctx: RequestContext = Depends(require_workspace_governance_ctx),
    service: SecurityService = Depends(get_security_service),
):
    """Update workspace-level rate limits and quotas."""
    handlers = SecurityHandlers(service)
    return await handlers.update_workspace_usage_policy(ctx, data)
