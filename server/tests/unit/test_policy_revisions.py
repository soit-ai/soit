"""test_policy_revisions

A policy that is only ever "the current value" cannot be cited: a run says it
was allowed and nobody can say what allowed it. These cover the revision
ledger, the identifier derived from policy content, and the restore path.
"""

import pytest

from app.kernel.commons.errors import NotFoundError, ValidationError
from app.kernel.security.policy_bundle import policy_bundle_id
from app.modules.identity.domain.models import Tenant, Workspace
from app.modules.security.application.schemas import (
    EgressPolicyUpdate,
    UsagePolicyUpdate,
)
from app.modules.security.application.service import SecurityService


class _Scope:
    """The identity port, answering with the rows this test wrote."""

    def __init__(self, tenant: Tenant, workspace: Workspace) -> None:
        self.tenant = tenant
        self.workspace = workspace

    def get_tenant(self, tenant_id: str):
        return self.tenant if self.tenant.id == tenant_id else None

    def get_workspace(self, workspace_id: str):
        return self.workspace if self.workspace.id == workspace_id else None


@pytest.fixture
def service(db, ctx) -> SecurityService:
    tenant = Tenant(id=ctx.tenant_id, name="Test tenant")
    workspace = Workspace(
        id=ctx.workspace_id,
        tenant_id=ctx.tenant_id,
        name="Test workspace",
        slug="test",
    )
    db.add(tenant)
    db.add(workspace)
    db.commit()
    return SecurityService(db, ctx, identity_policy_scope=_Scope(tenant, workspace))


def test_saving_a_policy_appends_a_revision(service: SecurityService):
    service.update_workspace_policy(EgressPolicyUpdate(allowlist=["api.stripe.com"]))
    service.update_workspace_policy(
        EgressPolicyUpdate(allowlist=["api.stripe.com", "api.twilio.com"])
    )

    revisions, _ = service.list_revisions("workspace")

    assert [row.revision for row in revisions] == [2, 1]
    assert revisions[0].document_json["egress_allowlist"] == [
        "api.stripe.com",
        "api.twilio.com",
    ]
    assert revisions[0].created_by == "test-user"


def test_limits_and_egress_rules_share_one_history(service: SecurityService):
    """A reviewer asks what a workspace could do, not which endpoint saved it."""
    service.update_workspace_policy(EgressPolicyUpdate(allowlist=["api.stripe.com"]))
    service.update_workspace_usage_policy(UsagePolicyUpdate(llm_daily_quota=500))

    revisions, _ = service.list_revisions("workspace")

    assert len(revisions) == 2
    latest = revisions[0].document_json
    assert latest["llm_daily_quota"] == 500
    assert latest["egress_allowlist"] == ["api.stripe.com"]


def test_the_bundle_identifier_follows_the_content_not_the_save(
    service: SecurityService,
):
    """Identical rules have to produce one identifier, or evidence is noise."""
    service.update_workspace_policy(EgressPolicyUpdate(allowlist=["a.example.com"]))
    first = service.active_bundle("workspace").bundle_id

    service.update_workspace_policy(EgressPolicyUpdate(allowlist=["b.example.com"]))
    changed = service.active_bundle("workspace").bundle_id

    service.update_workspace_policy(EgressPolicyUpdate(allowlist=["a.example.com"]))
    back = service.active_bundle("workspace").bundle_id

    assert first != changed
    assert back == first


def test_reordering_a_rule_list_is_not_a_policy_change(service: SecurityService):
    service.update_workspace_policy(EgressPolicyUpdate(allowlist=["a.com", "b.com"]))
    first = service.active_bundle("workspace").bundle_id

    service.update_workspace_policy(EgressPolicyUpdate(allowlist=["b.com", "a.com"]))

    assert service.active_bundle("workspace").bundle_id == first


def test_an_install_that_never_saved_still_has_an_identifier(
    service: SecurityService,
):
    """Revision 0 says the live policy matches no recorded revision."""
    bundle = service.active_bundle("workspace")

    assert bundle.revision == 0
    assert bundle.activated_at is None
    assert bundle.bundle_id.startswith("pb_")


def test_the_active_bundle_is_read_from_the_live_policy(service: SecurityService, db):
    """A policy changed outside the API must not be reported as the last save."""
    service.update_workspace_policy(EgressPolicyUpdate(allowlist=["a.example.com"]))
    workspace = service.get_workspace_policy()
    workspace.egress_allowlist = ["edited-by-hand.example.com"]
    db.flush()

    bundle = service.active_bundle("workspace")

    assert bundle.revision == 0
    assert bundle.bundle_id == policy_bundle_id(
        {
            "egress_allowlist": ["edited-by-hand.example.com"],
            "egress_blocklist": [],
            "llm_rate_limit_per_minute": None,
            "tool_rate_limit_per_minute": None,
            "llm_daily_quota": None,
            "tool_daily_quota": None,
        }
    )


def test_a_diff_names_only_the_fields_that_moved(service: SecurityService):
    service.update_workspace_policy(EgressPolicyUpdate(allowlist=["a.example.com"]))
    service.update_workspace_usage_policy(UsagePolicyUpdate(llm_daily_quota=200))

    diff = service.diff_revisions("workspace", from_revision=1, to_revision=2)

    assert [change.field for change in diff.changes] == ["llm_daily_quota"]
    assert diff.changes[0].before is None
    assert diff.changes[0].after == 200
    assert diff.from_bundle_id != diff.to_bundle_id


def test_a_save_that_changed_nothing_still_shows_as_a_save(service: SecurityService):
    service.update_workspace_policy(EgressPolicyUpdate(allowlist=["a.example.com"]))
    service.update_workspace_policy(EgressPolicyUpdate(allowlist=["a.example.com"]))

    revisions, _ = service.list_revisions("workspace")
    diff = service.diff_revisions("workspace", from_revision=1, to_revision=2)

    assert len(revisions) == 2
    assert diff.changes == []
    assert diff.from_bundle_id == diff.to_bundle_id


def test_a_rollback_restores_the_rules_and_appends_to_the_history(
    service: SecurityService,
):
    service.update_workspace_policy(EgressPolicyUpdate(allowlist=["safe.example.com"]))
    service.update_workspace_policy(EgressPolicyUpdate(allowlist=["*"]))
    revisions, _ = service.list_revisions("workspace")
    first = [row for row in revisions if row.revision == 1][0]

    bundle = service.rollback_to_revision(first.id)

    assert service.get_workspace_policy().egress_allowlist == ["safe.example.com"]
    assert bundle.revision == 3
    assert bundle.bundle_id == first.bundle_id

    history, _ = service.list_revisions("workspace")
    assert [row.revision for row in history] == [3, 2, 1]
    assert history[0].restored_from_revision == 1


def test_a_rollback_leaves_the_revision_it_restored_untouched(
    service: SecurityService,
):
    """History that could be rewritten would not be evidence of anything."""
    service.update_workspace_policy(EgressPolicyUpdate(allowlist=["safe.example.com"]))
    service.update_workspace_policy(EgressPolicyUpdate(allowlist=["*"]))
    revisions, _ = service.list_revisions("workspace")
    permissive = [row for row in revisions if row.revision == 2][0]
    first = [row for row in revisions if row.revision == 1][0]

    service.rollback_to_revision(first.id)

    assert permissive.document_json["egress_allowlist"] == ["*"]


def test_tenant_and_workspace_policies_have_separate_histories(
    service: SecurityService,
):
    service.update_workspace_policy(EgressPolicyUpdate(allowlist=["ws.example.com"]))
    service.update_tenant_policy(EgressPolicyUpdate(allowlist=["tenant.example.com"]))

    workspace_revisions, _ = service.list_revisions("workspace")
    tenant_revisions, _ = service.list_revisions("tenant")

    assert len(workspace_revisions) == 1
    assert len(tenant_revisions) == 1
    assert workspace_revisions[0].revision == 1
    assert tenant_revisions[0].revision == 1
    assert (
        workspace_revisions[0].bundle_id != tenant_revisions[0].bundle_id
    )


def test_an_unknown_scope_is_refused(service: SecurityService):
    with pytest.raises(ValidationError):
        service.active_bundle("global")


def test_an_unknown_revision_is_not_found(service: SecurityService):
    with pytest.raises(NotFoundError):
        service.rollback_to_revision("pr_missing")


def test_another_workspaces_revision_is_not_reachable(service: SecurityService, db):
    service.update_workspace_policy(EgressPolicyUpdate(allowlist=["a.example.com"]))
    revisions, _ = service.list_revisions("workspace")
    revisions[0].scope_id = "w_someone_else"
    db.flush()

    with pytest.raises(NotFoundError):
        service.get_revision(revisions[0].id)
