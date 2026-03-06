""" handlers

Security request handlers (thin orchestration).
"""

from typing import Optional

from app.kernel.contracts.context import RequestContext
from app.modules.security.application.service import SecurityService
from app.modules.security.application.schemas import (
    EgressPolicyUpdate,
    EgressPolicyResponse,
    EgressPolicyAuditResponse,
    UsagePolicyUpdate,
    UsagePolicyResponse,
)
from app.infra.db.pagination import PaginatedResponse, parse_page_params


class SecurityHandlers:
    """Handlers for security API endpoints."""

    def __init__(self, service: SecurityService):
        self.service = service

    async def get_tenant_policy(
        self,
        ctx: RequestContext,
    ) -> EgressPolicyResponse:
        tenant = self.service.get_tenant_policy()
        return EgressPolicyResponse(
            scope="tenant",
            allowlist=tenant.egress_allowlist or [],
            blocklist=tenant.egress_blocklist or [],
        )

    async def update_tenant_policy(
        self,
        ctx: RequestContext,
        data: EgressPolicyUpdate,
    ) -> EgressPolicyResponse:
        tenant = self.service.update_tenant_policy(data)
        return EgressPolicyResponse(
            scope="tenant",
            allowlist=tenant.egress_allowlist or [],
            blocklist=tenant.egress_blocklist or [],
        )

    async def get_workspace_policy(
        self,
        ctx: RequestContext,
    ) -> EgressPolicyResponse:
        workspace = self.service.get_workspace_policy()
        return EgressPolicyResponse(
            scope="workspace",
            allowlist=workspace.egress_allowlist or [],
            blocklist=workspace.egress_blocklist or [],
        )

    async def update_workspace_policy(
        self,
        ctx: RequestContext,
        data: EgressPolicyUpdate,
    ) -> EgressPolicyResponse:
        workspace = self.service.update_workspace_policy(data)
        return EgressPolicyResponse(
            scope="workspace",
            allowlist=workspace.egress_allowlist or [],
            blocklist=workspace.egress_blocklist or [],
        )

    async def list_audits(
        self,
        ctx: RequestContext,
        scope: Optional[str],
        page_token: Optional[str],
        page_size: int,
    ) -> PaginatedResponse[EgressPolicyAuditResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        limit_plus = limit + 1

        audits = self.service.list_audits(scope=scope, limit=limit_plus, offset=offset)
        has_next = len(audits) > limit
        audits = audits[:limit]
        items = [
            EgressPolicyAuditResponse(
                id=audit.id,
                tenant_id=audit.tenant_id,
                workspace_id=audit.workspace_id,
                scope=audit.scope,
                allowlist=audit.allowlist or [],
                blocklist=audit.blocklist or [],
                created_by=audit.created_by,
                created_at=audit.created_at,
            )
            for audit in audits
        ]
        next_offset = offset + len(audits) if has_next else None
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=next_offset,
        )

    async def get_tenant_usage_policy(
        self,
        ctx: RequestContext,
    ) -> UsagePolicyResponse:
        tenant = self.service.get_tenant_usage_policy()
        return UsagePolicyResponse(
            scope="tenant",
            llm_rate_limit_per_minute=tenant.llm_rate_limit_per_minute,
            tool_rate_limit_per_minute=tenant.tool_rate_limit_per_minute,
            llm_daily_quota=tenant.llm_daily_quota,
            tool_daily_quota=tenant.tool_daily_quota,
        )

    async def update_tenant_usage_policy(
        self,
        ctx: RequestContext,
        data: UsagePolicyUpdate,
    ) -> UsagePolicyResponse:
        tenant = self.service.update_tenant_usage_policy(data)
        return UsagePolicyResponse(
            scope="tenant",
            llm_rate_limit_per_minute=tenant.llm_rate_limit_per_minute,
            tool_rate_limit_per_minute=tenant.tool_rate_limit_per_minute,
            llm_daily_quota=tenant.llm_daily_quota,
            tool_daily_quota=tenant.tool_daily_quota,
        )

    async def get_workspace_usage_policy(
        self,
        ctx: RequestContext,
    ) -> UsagePolicyResponse:
        workspace = self.service.get_workspace_usage_policy()
        return UsagePolicyResponse(
            scope="workspace",
            llm_rate_limit_per_minute=workspace.llm_rate_limit_per_minute,
            tool_rate_limit_per_minute=workspace.tool_rate_limit_per_minute,
            llm_daily_quota=workspace.llm_daily_quota,
            tool_daily_quota=workspace.tool_daily_quota,
        )

    async def update_workspace_usage_policy(
        self,
        ctx: RequestContext,
        data: UsagePolicyUpdate,
    ) -> UsagePolicyResponse:
        workspace = self.service.update_workspace_usage_policy(data)
        return UsagePolicyResponse(
            scope="workspace",
            llm_rate_limit_per_minute=workspace.llm_rate_limit_per_minute,
            tool_rate_limit_per_minute=workspace.tool_rate_limit_per_minute,
            llm_daily_quota=workspace.llm_daily_quota,
            tool_daily_quota=workspace.tool_daily_quota,
        )
