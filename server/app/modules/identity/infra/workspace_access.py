"""Database-backed workspace access resolution."""

from datetime import UTC

from app.infra.db.session import get_db_sync
from app.kernel.commons.errors import UnauthorizedError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.workspace_access import WorkspaceAccess
from app.modules.identity.infra.repository import (
    TenantMembershipRepository,
    TenantRepository,
    UserSessionRepository,
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
        session_id: str | None = None,
    ) -> WorkspaceAccess | None:
        """Return access only when tenant, workspace, and membership all exist.

        When the caller's token names a session, that session must still be
        live. It is checked here rather than in a separate lookup because this
        is already the one database read every authenticated request makes, and
        checking it at refresh time alone would leave a signed-out token working
        until it expired.
        """
        context = RequestContext(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        db = get_db_sync()
        try:
            if session_id:
                self._require_live_session(db, str(session_id))
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

    @staticmethod
    def _require_live_session(db, session_id: str) -> None:
        """Raise when the session behind a token has ended or expired.

        A token with no session id predates sessions and is never routed here;
        it stays valid until it expires, so shipping this does not sign
        everybody out.
        """
        session = UserSessionRepository(db).get_by_id(session_id)
        if session is None or session.status != "active":
            raise UnauthorizedError("Session has ended")
        expires_at = session.expires_at
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= utc_now():
                raise UnauthorizedError("Session has expired")
