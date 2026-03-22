"""test_security_service

Unit tests for SecurityService.
"""

from app.kernel.contracts.context import RequestContext
from app.modules.identity.domain.models import (
    Tenant,
    Workspace,
    generate_tenant_id,
    generate_workspace_id,
)
from app.modules.security.application.schemas import EgressPolicyUpdate, UsagePolicyUpdate
from app.modules.security.application.service import SecurityService


def _seed_tenant_workspace(db):
    tenant_id = generate_tenant_id()
    workspace_id = generate_workspace_id()
    tenant = Tenant(id=tenant_id, name="tenant-1", plan="free")
    workspace = Workspace(
        id=workspace_id,
        tenant_id=tenant_id,
        name="workspace-1",
        description="demo",
    )
    db.add(tenant)
    db.add(workspace)
    db.commit()
    return tenant_id, workspace_id


def test_security_policy_updates_and_audits(db):
    """Update policies and confirm audit records."""
    tenant_id, workspace_id = _seed_tenant_workspace(db)
    ctx = RequestContext(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        user_id="user_1",
        tenant_role="Owner",
        workspace_role="Owner",
    )
    service = SecurityService(db, ctx)

    tenant_policy = service.update_tenant_policy(
        EgressPolicyUpdate(
            allowlist=["example.com"],
            blocklist=["*.blocked.com"],
        )
    )
    assert tenant_policy.egress_allowlist == ["example.com"]
    assert tenant_policy.egress_blocklist == ["*.blocked.com"]

    workspace_policy = service.update_workspace_policy(
        EgressPolicyUpdate(
            allowlist=["workspace.com"],
            blocklist=["*.workspace-blocked.com"],
        )
    )
    assert workspace_policy.egress_allowlist == ["workspace.com"]
    assert workspace_policy.egress_blocklist == ["*.workspace-blocked.com"]

    tenant_audits = service.list_audits(scope="tenant", limit=10, offset=0)
    workspace_audits = service.list_audits(scope="workspace", limit=10, offset=0)

    assert len(tenant_audits) == 1
    assert tenant_audits[0].scope == "tenant"
    assert len(workspace_audits) == 1
    assert workspace_audits[0].scope == "workspace"

    tenant_limits = service.update_tenant_usage_policy(
        UsagePolicyUpdate(
            llm_rate_limit_per_minute=120,
            tool_rate_limit_per_minute=300,
            llm_daily_quota=2000,
            tool_daily_quota=5000,
        )
    )
    assert tenant_limits.llm_rate_limit_per_minute == 120
    assert tenant_limits.tool_rate_limit_per_minute == 300

    workspace_limits = service.update_workspace_usage_policy(
        UsagePolicyUpdate(
            llm_rate_limit_per_minute=60,
            tool_daily_quota=100,
        )
    )
    assert workspace_limits.llm_rate_limit_per_minute == 60
    assert workspace_limits.tool_daily_quota == 100
