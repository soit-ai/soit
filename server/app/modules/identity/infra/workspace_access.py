"""Database-backed workspace access resolution."""

from datetime import UTC, datetime

from sqlalchemy import and_, exists, select

from app.infra.db.session import get_async_session_local
from app.kernel.commons.errors import ForbiddenError, UnauthorizedError
from app.kernel.commons.time import utc_now
from app.kernel.identity.workspace_access import WorkspaceAccess
from app.modules.identity.domain.models import (
    Tenant,
    TenantMembership,
    UserMfa,
    UserSession,
    Workspace,
    WorkspaceMembership,
)
from app.modules.identity.infra.repository import UserSessionRepository


def tighter_limit(workspace_value: int | None, tenant_value: int | None) -> int | None:
    """The stricter of a workspace limit and its tenant's; None means unlimited."""
    if workspace_value is None:
        return tenant_value
    if tenant_value is None:
        return workspace_value
    return min(workspace_value, tenant_value)


class DatabaseWorkspaceAccessResolver:
    """Resolve membership and effective quotas from the primary database."""

    async def resolve(
        self,
        tenant_id: str | None,
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

        Everything is fetched in one round trip: the memberships and both
        scope rows are outer-joined onto the tenant, the session and the
        second-factor enrolment ride along as scalar subqueries. Five primary
        key reads in sequence were the largest fixed cost of every request.
        """
        db = get_async_session_local()()
        try:
            row = (
                await db.execute(self._access_query(tenant_id, workspace_id, user_id, session_id))
            ).one_or_none()
            if row is None:
                # No such tenant. A dead session still answers 401, not 403.
                if session_id:
                    await self._require_live_session(db, str(session_id))
                return None
            (
                session_status,
                session_expires_at,
                resolved_tenant_id,
                tenant_role,
                workspace_role,
                tenant_llm_rate,
                tenant_tool_rate,
                tenant_llm_quota,
                tenant_tool_quota,
                workspace_present,
                workspace_llm_rate,
                workspace_tool_rate,
                workspace_llm_quota,
                workspace_tool_quota,
                require_mfa,
                content_capture,
                mfa_active,
            ) = row
            if session_id:
                self._check_session(session_status, session_expires_at)
            if tenant_role is None or workspace_role is None or workspace_present is None:
                return None

            if require_mfa and not mfa_active:
                # A distinct error from "not a member": the person belongs here
                # and needs to enrol, which the console can only offer if it can
                # tell the two apart.
                raise ForbiddenError(
                    "This workspace requires two-factor authentication",
                    {"reason": "mfa_required", "workspace_id": workspace_id},
                )

            # The tenant's limits are a ceiling: a workspace may tighten them
            # but never loosen them, so a workspace admin cannot buy back what
            # the organization took away.
            return WorkspaceAccess(
                tenant_role=tenant_role,
                workspace_role=workspace_role,
                llm_rate_limit_per_minute=tighter_limit(workspace_llm_rate, tenant_llm_rate),
                tool_rate_limit_per_minute=tighter_limit(workspace_tool_rate, tenant_tool_rate),
                llm_daily_quota=tighter_limit(workspace_llm_quota, tenant_llm_quota),
                tool_daily_quota=tighter_limit(workspace_tool_quota, tenant_tool_quota),
                content_capture=content_capture or "full",
                tenant_id=resolved_tenant_id,
            )
        finally:
            await db.close()

    @staticmethod
    def _access_query(
        tenant_id: str | None, workspace_id: str, user_id: str, session_id: str | None
    ):
        session_key = str(session_id or "")
        session_status = (
            select(UserSession.status).where(UserSession.id == session_key).scalar_subquery()
        )
        session_expires_at = (
            select(UserSession.expires_at).where(UserSession.id == session_key).scalar_subquery()
        )
        # Without a pinned tenant the workspace names it: its id is unique
        # across tenants, so this is the only tenant it can belong to.
        workspace_tenant = (
            select(Workspace.tenant_id).where(Workspace.id == workspace_id).scalar_subquery()
        )
        mfa_active = exists(
            select(UserMfa.user_id).where(
                and_(UserMfa.user_id == user_id, UserMfa.status == "active")
            )
        )
        return (
            select(
                session_status,
                session_expires_at,
                Tenant.id,
                TenantMembership.role,
                WorkspaceMembership.role,
                Tenant.llm_rate_limit_per_minute,
                Tenant.tool_rate_limit_per_minute,
                Tenant.llm_daily_quota,
                Tenant.tool_daily_quota,
                Workspace.id,
                Workspace.llm_rate_limit_per_minute,
                Workspace.tool_rate_limit_per_minute,
                Workspace.llm_daily_quota,
                Workspace.tool_daily_quota,
                Workspace.require_mfa,
                Workspace.content_capture,
                mfa_active,
            )
            .select_from(Tenant)
            .outerjoin(
                TenantMembership,
                and_(
                    TenantMembership.tenant_id == Tenant.id,
                    TenantMembership.user_id == user_id,
                ),
            )
            .outerjoin(
                Workspace,
                and_(Workspace.id == workspace_id, Workspace.tenant_id == Tenant.id),
            )
            .outerjoin(
                WorkspaceMembership,
                and_(
                    WorkspaceMembership.tenant_id == Tenant.id,
                    WorkspaceMembership.workspace_id == workspace_id,
                    WorkspaceMembership.user_id == user_id,
                ),
            )
            .where(Tenant.id == (tenant_id if tenant_id is not None else workspace_tenant))
        )

    @staticmethod
    def _check_session(status: str | None, expires_at: datetime | str | None) -> None:
        """Raise when the session behind a token has ended or expired."""
        if status is None or status != "active":
            raise UnauthorizedError("Session has ended")
        if expires_at is not None:
            if isinstance(expires_at, str):
                # SQLite hands a scalar subquery's datetime back as text.
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= utc_now():
                raise UnauthorizedError("Session has expired")

    @staticmethod
    async def _require_live_session(db, session_id: str) -> None:
        """Raise when the session behind a token has ended or expired.

        A token with no session id predates sessions and is never routed here;
        it stays valid until it expires, so shipping this does not sign
        everybody out.
        """
        session = await UserSessionRepository(db).get_by_id(session_id)
        if session is None or session.status != "active":
            raise UnauthorizedError("Session has ended")
        expires_at = session.expires_at
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= utc_now():
                raise UnauthorizedError("Session has expired")
