""" router

Security API routes (FastAPI).
"""


from datetime import datetime

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
    EgressBlockSummaryResponse,
    EgressPolicyAuditResponse,
    EgressPolicyResponse,
    EgressPolicyUpdate,
    PolicyBundleResponse,
    PolicyRevisionDiff,
    PolicyRevisionResponse,
    PolicyRollbackRequest,
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


@router.get("/egress/blocks", response_model=EgressBlockSummaryResponse)
async def summarize_egress_blocks(
    since: datetime | None = None,
    until: datetime | None = None,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: SecurityService = Depends(get_security_service),
):
    """Summarize outbound requests the policy refused inside a window.

    Distinct from /egress/audits, which records changes to the policy itself.
    """
    handlers = SecurityHandlers(service)
    return await handlers.summarize_egress_blocks(ctx, since=since, until=until)


@router.get("/policies/bundle", response_model=PolicyBundleResponse)
async def get_policy_bundle(
    scope: str = "workspace",
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: SecurityService = Depends(get_security_service),
):
    """Return the identifier of the policy a call would be evaluated against.

    The same identifier is recorded on refused outbound requests, so evidence
    can be matched to the rules that produced it.
    """
    handlers = SecurityHandlers(service)
    return await handlers.get_policy_bundle(ctx, scope)


@router.get("/policies/revisions", response_model=PaginatedResponse[PolicyRevisionResponse])
async def list_policy_revisions(
    scope: str = "workspace",
    page_token: str | None = None,
    page_size: int = 20,
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: SecurityService = Depends(get_security_service),
):
    """List a scope's policy activation history, newest first."""
    handlers = SecurityHandlers(service)
    return await handlers.list_policy_revisions(ctx, scope, page_token, page_size)


@router.get("/policies/revisions/diff", response_model=PolicyRevisionDiff)
async def diff_policy_revisions(
    from_revision: int,
    to_revision: int,
    scope: str = "workspace",
    ctx: RequestContext = Depends(require_workspace_read_ctx),
    service: SecurityService = Depends(get_security_service),
):
    """Report what changed between two revisions of one scope."""
    handlers = SecurityHandlers(service)
    return await handlers.diff_policy_revisions(ctx, scope, from_revision, to_revision)


@router.post("/policies/revisions/{revision_id}/rollback", response_model=PolicyBundleResponse)
async def rollback_policy_revision(
    revision_id: str,
    data: PolicyRollbackRequest | None = None,
    ctx: RequestContext = Depends(require_workspace_governance_ctx),
    service: SecurityService = Depends(get_security_service),
):
    """Put an earlier revision's policy back in force.

    Restoring is itself a policy change: it needs the same authority as making
    one, and it appends to the history rather than rewinding it.
    """
    handlers = SecurityHandlers(service)
    return await handlers.rollback_policy_revision(
        ctx, revision_id, data.note if data else None
    )


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
