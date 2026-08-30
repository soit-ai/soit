""" handlers

Security request handlers (thin orchestration).
"""

from datetime import datetime

from app.infra.db.pagination import PaginatedResponse, parse_page_params
from app.kernel.contracts.context import RequestContext
from app.modules.security.application.schemas import (
    EgressBlockSummaryResponse,
    EgressPolicyAuditResponse,
    EgressPolicyResponse,
    EgressPolicyUpdate,
    PolicyBundleResponse,
    PolicyDocument,
    PolicyRevisionDiff,
    PolicyRevisionResponse,
    UsagePolicyResponse,
    UsagePolicyUpdate,
)
from app.modules.security.application.service import SecurityService


class SecurityHandlers:
    """Handlers for security API endpoints."""

    def __init__(self, service: SecurityService):
        self.service = service

    async def summarize_egress_blocks(
        self,
        ctx: RequestContext,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> EgressBlockSummaryResponse:
        """Summarize refused outbound requests inside a window."""
        return self.service.summarize_egress_blocks(since=since, until=until)

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
        scope: str | None,
        page_token: str | None,
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

    # ------------------------------------------------------------------
    # Policy revisions
    # ------------------------------------------------------------------

    async def get_policy_bundle(
        self,
        ctx: RequestContext,
        scope: str,
    ) -> PolicyBundleResponse:
        """Return the identifier of the policy currently in force."""
        return self.service.active_bundle(scope)

    async def list_policy_revisions(
        self,
        ctx: RequestContext,
        scope: str,
        page_token: str | None,
        page_size: int,
    ) -> PaginatedResponse[PolicyRevisionResponse]:
        limit, token_obj = parse_page_params(page_token, page_size)
        offset = token_obj.offset if token_obj else 0
        revisions, active_bundle_id = self.service.list_revisions(
            scope, limit=limit + 1, offset=offset
        )
        has_next = len(revisions) > limit
        revisions = revisions[:limit]
        items = [
            PolicyRevisionResponse(
                id=revision.id,
                scope=revision.scope,
                scope_id=revision.scope_id,
                revision=revision.revision,
                bundle_id=revision.bundle_id,
                document=PolicyDocument(**(revision.document_json or {})),
                note=revision.note,
                restored_from_revision=revision.restored_from_revision,
                created_by=revision.created_by,
                created_at=revision.created_at,
                # Several revisions can carry the same content; the newest of
                # them is the one in force, and the rest are history.
                active=(
                    revision.bundle_id == active_bundle_id
                    and revision.revision == max(row.revision for row in revisions)
                ),
            )
            for revision in revisions
        ]
        return PaginatedResponse.create(
            items=items,
            page_size=len(items),
            has_next=has_next,
            next_offset=offset + len(revisions) if has_next else None,
        )

    async def diff_policy_revisions(
        self,
        ctx: RequestContext,
        scope: str,
        from_revision: int,
        to_revision: int,
    ) -> PolicyRevisionDiff:
        return self.service.diff_revisions(
            scope, from_revision=from_revision, to_revision=to_revision
        )

    async def rollback_policy_revision(
        self,
        ctx: RequestContext,
        revision_id: str,
        note: str | None,
    ) -> PolicyBundleResponse:
        return self.service.rollback_to_revision(revision_id, note=note)

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
