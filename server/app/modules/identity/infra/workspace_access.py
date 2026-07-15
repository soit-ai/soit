"""Database-backed workspace access resolution."""

from app.infra.db.session import get_db_sync
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.workspace_access import WorkspaceAccess
from app.modules.identity.infra.repository import (
    TenantMembershipRepository,
    TenantRepository,
    WorkspaceMembershipRepository,
    WorkspaceRepository,
)


class DatabaseWorkspaceAccessResolver:
    """Resolve membership and effective quotas from the primary database."""

    def resolve(
        self,
        tenant_id: str,
        workspace_id: str,
        user_id: str,
    ) -> WorkspaceAccess | None:
        """Return access only when tenant, workspace, and membership all exist."""
        context = RequestContext(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        db = get_db_sync()
        try:
            tenant_membership = TenantMembershipRepository(db).get(tenant_id, user_id)
            if tenant_membership is None:
                return None

            membership = WorkspaceMembershipRepository(db, context).get(
                workspace_id,
                user_id,
            )
            if membership is None:
                return None

            tenant = TenantRepository(db).get_by_id(tenant_id)
            workspace = WorkspaceRepository(db, context).get_by_id(workspace_id)
            if tenant is None or workspace is None:
                return None

            return WorkspaceAccess(
                tenant_role=tenant_membership.role,
                workspace_role=membership.role,
                llm_rate_limit_per_minute=(
                    workspace.llm_rate_limit_per_minute
                    if workspace.llm_rate_limit_per_minute is not None
                    else tenant.llm_rate_limit_per_minute
                ),
                tool_rate_limit_per_minute=(
                    workspace.tool_rate_limit_per_minute
                    if workspace.tool_rate_limit_per_minute is not None
                    else tenant.tool_rate_limit_per_minute
                ),
                llm_daily_quota=(
                    workspace.llm_daily_quota
                    if workspace.llm_daily_quota is not None
                    else tenant.llm_daily_quota
                ),
                tool_daily_quota=(
                    workspace.tool_daily_quota
                    if workspace.tool_daily_quota is not None
                    else tenant.tool_daily_quota
                ),
            )
        finally:
            db.close()
