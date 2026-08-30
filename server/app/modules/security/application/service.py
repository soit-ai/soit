""" service

Security domain service.
"""


from datetime import datetime

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.security.egress import EGRESS_BLOCK_EVENT_TYPE
from app.modules.identity.application.contracts import IdentityPolicyScopePort
from app.modules.security.application.schemas import (
    EgressBlockRow,
    EgressBlockSummaryResponse,
    EgressPolicyUpdate,
    UsagePolicyUpdate,
)


class SecurityService:
    """Security service for egress policy management."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        identity_policy_scope: IdentityPolicyScopePort,
    ):
        self.db = db
        self.ctx = ctx
        self.identity_policy_scope = identity_policy_scope

    @staticmethod
    def _unwrap_all(results):
        """Unwrap SQLAlchemy row results to model instances."""
        if not results:
            return []
        first = results[0]
        if isinstance(first, list | tuple) or hasattr(first, "_mapping"):
            return [item[0] for item in results]
        return results

    def get_tenant_policy(self):
        tenant = self.identity_policy_scope.get_tenant(self.ctx.tenant_id)
        if not tenant:
            raise NotFoundError(f"Tenant not found: {self.ctx.tenant_id}")
        return tenant

    def update_tenant_policy(self, data: EgressPolicyUpdate):
        tenant = self.get_tenant_policy()
        tenant.egress_allowlist = list(data.allowlist or [])
        tenant.egress_blocklist = list(data.blocklist or [])
        tenant.updated_at = utc_now()
        self.db.flush()
        self.db.refresh(tenant)
        self._log_audit(
            scope="tenant",
            workspace_id=None,
            allowlist=tenant.egress_allowlist,
            blocklist=tenant.egress_blocklist,
        )
        return tenant

    def get_workspace_policy(self):
        workspace = self.identity_policy_scope.get_workspace(self.ctx.workspace_id)
        if not workspace:
            raise NotFoundError(f"Workspace not found: {self.ctx.workspace_id}")
        return workspace

    def update_workspace_policy(self, data: EgressPolicyUpdate):
        workspace = self.get_workspace_policy()
        workspace.egress_allowlist = list(data.allowlist or [])
        workspace.egress_blocklist = list(data.blocklist or [])
        workspace.updated_at = utc_now()
        self.db.flush()
        self.db.refresh(workspace)
        self._log_audit(
            scope="workspace",
            workspace_id=workspace.id,
            allowlist=workspace.egress_allowlist,
            blocklist=workspace.egress_blocklist,
        )
        return workspace

    def list_audits(
        self,
        *,
        scope: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditEvent]:
        clauses = [
            AuditEvent.tenant_id == self.ctx.tenant_id,
            AuditEvent.event_type == "security.egress_policy.updated",
            AuditEvent.resource_type == "egress_policy",
        ]
        if scope:
            clauses.append(AuditEvent.scope == scope)
        if scope == "workspace":
            clauses.append(AuditEvent.workspace_id == self.ctx.workspace_id)

        query = (
            select(AuditEvent)
            .where(and_(*clauses))
            .order_by(desc(AuditEvent.created_at))
            .offset(offset)
            .limit(limit)
        )
        rows = list(self.db.exec(query).all())
        return self._unwrap_all(rows)

    def summarize_egress_blocks(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        recent_limit: int = 20,
    ) -> EgressBlockSummaryResponse:
        """Count refused outbound requests, and return the most recent ones.

        The count and the evidence come from the same audit rows, so a figure
        on the governance panel can always be opened and read.
        """
        clauses = [
            AuditEvent.tenant_id == self.ctx.tenant_id,
            AuditEvent.workspace_id == self.ctx.workspace_id,
            AuditEvent.event_type == EGRESS_BLOCK_EVENT_TYPE,
        ]
        if since:
            clauses.append(AuditEvent.created_at >= since)
        if until:
            clauses.append(AuditEvent.created_at <= until)

        query = (
            select(AuditEvent)
            .where(and_(*clauses))
            .order_by(desc(AuditEvent.created_at))
        )
        rows = self._unwrap_all(list(self.db.exec(query).all()))

        subjects: set[str] = set()
        domains: set[str] = set()
        recent: list[EgressBlockRow] = []
        for row in rows:
            payload = row.payload_json if isinstance(row.payload_json, dict) else {}
            resource_ref = payload.get("resource_ref")
            if resource_ref:
                subjects.add(str(resource_ref))
            if row.resource_id:
                domains.add(str(row.resource_id))
            if len(recent) < recent_limit:
                recent.append(
                    EgressBlockRow(
                        id=row.id,
                        domain=row.resource_id,
                        resource_ref=resource_ref,
                        reason=payload.get("reason"),
                        url=payload.get("url"),
                        actor_user_id=row.actor_user_id,
                        trace_id=row.trace_id,
                        created_at=row.created_at,
                    )
                )

        return EgressBlockSummaryResponse(
            since=since,
            until=until,
            total=len(rows),
            subjects=len(subjects),
            domains=len(domains),
            recent=recent,
        )

    def _log_audit(
        self,
        *,
        scope: str,
        workspace_id: str | None,
        allowlist: list[str],
        blocklist: list[str],
    ) -> None:
        audit = AuditEvent(
            tenant_id=self.ctx.tenant_id,
            workspace_id=workspace_id,
            event_type="security.egress_policy.updated",
            resource_type="egress_policy",
            resource_id=scope,
            operation="update",
            actor_user_id=self.ctx.user_id,
            scope=scope,
            payload_json={"allowlist": allowlist, "blocklist": blocklist},
        )
        self.db.add(audit)
        self.db.flush()
        self.db.refresh(audit)

    def get_tenant_usage_policy(self):
        tenant = self.get_tenant_policy()
        return tenant

    def update_tenant_usage_policy(self, data: UsagePolicyUpdate):
        tenant = self.get_tenant_policy()
        updates = data.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(tenant, key, value)
        tenant.updated_at = utc_now()
        self.db.flush()
        self.db.refresh(tenant)
        return tenant

    def get_workspace_usage_policy(self):
        workspace = self.get_workspace_policy()
        return workspace

    def update_workspace_usage_policy(self, data: UsagePolicyUpdate):
        workspace = self.get_workspace_policy()
        updates = data.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(workspace, key, value)
        workspace.updated_at = utc_now()
        self.db.flush()
        self.db.refresh(workspace)
        return workspace
