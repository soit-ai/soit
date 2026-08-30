""" service

Security domain service.
"""


from datetime import datetime

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.security.egress import EGRESS_BLOCK_EVENT_TYPE
from app.kernel.security.policy_bundle import policy_bundle_id
from app.modules.identity.application.contracts import IdentityPolicyScopePort
from app.modules.security.application.schemas import (
    EgressBlockRow,
    EgressBlockSummaryResponse,
    EgressPolicyUpdate,
    PolicyBundleResponse,
    PolicyDocument,
    PolicyFieldChange,
    PolicyRevisionDiff,
    UsagePolicyUpdate,
)
from app.modules.security.domain.models import PolicyRevision


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
        self.record_revision("tenant", tenant)
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
        self.record_revision("workspace", workspace)
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
                        tenant_bundle_id=payload.get("tenant_bundle_id"),
                        workspace_bundle_id=payload.get("workspace_bundle_id"),
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

    # ------------------------------------------------------------------
    # Policy revisions
    #
    # A policy that is only ever "the current value" cannot be cited. Every
    # save appends a revision, so an operator can read what a scope was
    # allowed to do at any point, compare two of those points, and put an
    # earlier one back without retyping it.
    # ------------------------------------------------------------------

    def _scope_entity(self, scope: str):
        """Return the tenant or workspace a scope name refers to."""
        if scope == "tenant":
            return self.get_tenant_policy()
        if scope == "workspace":
            return self.get_workspace_policy()
        raise ValidationError(
            "Policy scope must be 'tenant' or 'workspace'",
            {"scope": scope},
        )

    @staticmethod
    def _document(entity) -> PolicyDocument:
        """Read the governed policy off a tenant or workspace."""
        return PolicyDocument(
            egress_allowlist=list(entity.egress_allowlist or []),
            egress_blocklist=list(entity.egress_blocklist or []),
            llm_rate_limit_per_minute=entity.llm_rate_limit_per_minute,
            tool_rate_limit_per_minute=entity.tool_rate_limit_per_minute,
            llm_daily_quota=entity.llm_daily_quota,
            tool_daily_quota=entity.tool_daily_quota,
        )

    @staticmethod
    def bundle_id_for(entity) -> str | None:
        """Return the bundle identifier of a tenant or workspace as it stands.

        Used where a policy is read for enforcement rather than for display, so
        the decision and the identifier recorded with it come from one read.
        """
        if entity is None:
            return None
        return policy_bundle_id(SecurityService._document(entity).model_dump())

    def _latest_revision(self, scope: str, scope_id: str) -> PolicyRevision | None:
        query = (
            select(PolicyRevision)
            .where(
                and_(
                    PolicyRevision.tenant_id == self.ctx.tenant_id,
                    PolicyRevision.scope == scope,
                    PolicyRevision.scope_id == scope_id,
                )
            )
            .order_by(desc(PolicyRevision.revision))
            .limit(1)
        )
        rows = self._unwrap_all(list(self.db.exec(query).all()))
        return rows[0] if rows else None

    def record_revision(
        self,
        scope: str,
        entity,
        *,
        note: str | None = None,
        restored_from_revision: int | None = None,
    ) -> PolicyRevision:
        """Append the scope's current policy as the next revision.

        Saving the same content twice still appends: the record is of what was
        decided, not only of what differed. The bundle identifier repeating is
        how "nothing actually changed" stays visible.
        """
        scope_id = entity.id
        document = self._document(entity)
        previous = self._latest_revision(scope, scope_id)
        revision = PolicyRevision(
            tenant_id=self.ctx.tenant_id,
            scope=scope,
            scope_id=scope_id,
            workspace_id=scope_id if scope == "workspace" else None,
            revision=(previous.revision + 1) if previous else 1,
            bundle_id=policy_bundle_id(document.model_dump()),
            document_json=document.model_dump(),
            note=note,
            restored_from_revision=restored_from_revision,
            created_by=self.ctx.user_id,
        )
        self.db.add(revision)
        self.db.flush()
        self.db.refresh(revision)
        return revision

    def active_bundle(self, scope: str) -> PolicyBundleResponse:
        """Return the identifier of the policy in force for a scope.

        The identifier is derived from the live policy, never from the last row
        written, so it stays true even when the policy was changed by a
        migration or by hand. Revision 0 means the live policy matches no
        recorded revision, which is the honest answer for an install that has
        never saved one.
        """
        entity = self._scope_entity(scope)
        document = self._document(entity)
        bundle_id = policy_bundle_id(document.model_dump())
        latest = self._latest_revision(scope, entity.id)
        matched = latest if latest is not None and latest.bundle_id == bundle_id else None
        return PolicyBundleResponse(
            scope=scope,
            scope_id=entity.id,
            bundle_id=bundle_id,
            revision=matched.revision if matched else 0,
            document=document,
            activated_at=matched.created_at if matched else None,
            activated_by=matched.created_by if matched else None,
        )

    def list_revisions(
        self,
        scope: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[PolicyRevision], str]:
        """Return a scope's activation history, newest first, and what is live.

        The live bundle identifier travels with the rows so a reader can tell
        which entry is in force without a second request that could disagree
        with the first.
        """
        entity = self._scope_entity(scope)
        query = (
            select(PolicyRevision)
            .where(
                and_(
                    PolicyRevision.tenant_id == self.ctx.tenant_id,
                    PolicyRevision.scope == scope,
                    PolicyRevision.scope_id == entity.id,
                )
            )
            .order_by(desc(PolicyRevision.revision))
            .offset(offset)
            .limit(limit)
        )
        rows = self._unwrap_all(list(self.db.exec(query).all()))
        return rows, policy_bundle_id(self._document(entity).model_dump())

    def get_revision(self, revision_id: str) -> PolicyRevision:
        query = select(PolicyRevision).where(
            and_(
                PolicyRevision.tenant_id == self.ctx.tenant_id,
                PolicyRevision.id == revision_id,
            )
        )
        rows = self._unwrap_all(list(self.db.exec(query).all()))
        if not rows:
            raise NotFoundError(f"Policy revision not found: {revision_id}")
        revision = rows[0]
        # A workspace revision belongs to one workspace; the request context
        # decides which, so another workspace's history is not readable here.
        if revision.scope == "workspace" and revision.scope_id != self.ctx.workspace_id:
            raise NotFoundError(f"Policy revision not found: {revision_id}")
        return revision

    def _revision_by_number(self, scope: str, scope_id: str, number: int) -> PolicyRevision:
        query = select(PolicyRevision).where(
            and_(
                PolicyRevision.tenant_id == self.ctx.tenant_id,
                PolicyRevision.scope == scope,
                PolicyRevision.scope_id == scope_id,
                PolicyRevision.revision == number,
            )
        )
        rows = self._unwrap_all(list(self.db.exec(query).all()))
        if not rows:
            raise NotFoundError(f"Policy revision not found: {scope} r{number}")
        return rows[0]

    def diff_revisions(
        self,
        scope: str,
        *,
        from_revision: int,
        to_revision: int,
    ) -> PolicyRevisionDiff:
        """Report what changed between two revisions of one scope."""
        entity = self._scope_entity(scope)
        before = self._revision_by_number(scope, entity.id, from_revision)
        after = self._revision_by_number(scope, entity.id, to_revision)
        before_doc = PolicyDocument(**(before.document_json or {})).model_dump()
        after_doc = PolicyDocument(**(after.document_json or {})).model_dump()

        changes: list[PolicyFieldChange] = []
        for field in PolicyDocument.model_fields:
            old_value = before_doc.get(field)
            new_value = after_doc.get(field)
            if isinstance(old_value, list) and isinstance(new_value, list):
                # Rule order is not policy, so reordering is not a change.
                if sorted(old_value) == sorted(new_value):
                    continue
            elif old_value == new_value:
                continue
            changes.append(PolicyFieldChange(field=field, before=old_value, after=new_value))

        return PolicyRevisionDiff(
            scope=scope,
            from_revision=before.revision,
            to_revision=after.revision,
            from_bundle_id=before.bundle_id,
            to_bundle_id=after.bundle_id,
            changes=changes,
        )

    def rollback_to_revision(
        self,
        revision_id: str,
        *,
        note: str | None = None,
    ) -> PolicyBundleResponse:
        """Put an earlier revision's policy back in force.

        Nothing is rewritten or removed: the restored content is appended as a
        new revision naming what it restored. A history that could be edited
        would not be evidence of anything.
        """
        source = self.get_revision(revision_id)
        entity = self._scope_entity(source.scope)
        document = PolicyDocument(**(source.document_json or {}))

        entity.egress_allowlist = list(document.egress_allowlist)
        entity.egress_blocklist = list(document.egress_blocklist)
        entity.llm_rate_limit_per_minute = document.llm_rate_limit_per_minute
        entity.tool_rate_limit_per_minute = document.tool_rate_limit_per_minute
        entity.llm_daily_quota = document.llm_daily_quota
        entity.tool_daily_quota = document.tool_daily_quota
        entity.updated_at = utc_now()
        self.db.flush()
        self.db.refresh(entity)

        self._log_audit(
            scope=source.scope,
            workspace_id=entity.id if source.scope == "workspace" else None,
            allowlist=list(document.egress_allowlist),
            blocklist=list(document.egress_blocklist),
        )
        self.record_revision(
            source.scope,
            entity,
            note=note or f"Restored revision {source.revision}",
            restored_from_revision=source.revision,
        )
        return self.active_bundle(source.scope)

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
        self.record_revision("tenant", tenant)
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
        self.record_revision("workspace", workspace)
        return workspace
