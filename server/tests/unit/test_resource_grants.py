"""test_resource_grants

Unit tests for resource-level grants.
"""

import pytest
from sqlmodel import select

from app.kernel.contracts.context import RequestContext
from app.kernel.identity.permissions import (
    check_resource_permission,
    register_resource_grant_provider,
)
from app.kernel.runtime.db.models.audit import AuditEvent
from app.modules.identity.domain.models import ResourceGrant
from app.modules.identity.infra.repository import ResourceGrantRepository


class _ResourceGrantProvider:
    def __init__(self, db) -> None:
        self.db = db

    def allows_resource_action(
        self,
        *,
        ctx: RequestContext,
        resource_type: str,
        resource_id: str,
        action: str,
        effective_action: str,
    ) -> bool:
        grant = ResourceGrantRepository(self.db, ctx).get_by_resource_user(resource_type, resource_id, ctx.user_id)
        if not grant:
            return False
        allowed_actions = {str(item).strip().lower() for item in (grant.actions or [])}
        return "*" in allowed_actions or action in allowed_actions or effective_action in allowed_actions


@pytest.mark.asyncio
async def test_resource_grant_allows_action(monkeypatch, db):
    """Resource grant allows elevated actions."""
    from app.infra.db import session as session_module

    monkeypatch.setattr(session_module, "get_db_sync", lambda: db)
    register_resource_grant_provider(_ResourceGrantProvider(db))

    ctx = RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        user_id="user-1",
        workspace_role="Viewer",
    )

    repo = ResourceGrantRepository(db, ctx)
    repo.create(
        ResourceGrant(
            resource_type="knowledge",
            resource_id="kb-1",
            user_id=ctx.user_id,
            actions=["WRITE"],
        )
    )
    repo.create(
        ResourceGrant(
            resource_type="workflow",
            resource_id="wf-1",
            user_id=ctx.user_id,
            actions=["run"],
        )
    )

    await check_resource_permission(ctx, "knowledge", "kb-1", "update")
    await check_resource_permission(ctx, "workflow", "wf-1", "run")


def test_resource_grant_audit_events_are_written(client, db):
    """Resource grant writes use the unified audit_events table."""
    response = client.post(
        "/api/v1/resource-grants",
        headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        json={
            "resource_type": "knowledge",
            "resource_id": "kb-audit",
            "user_id": "user-audit",
            "actions": ["read", "write"],
        },
    )

    assert response.status_code == 200
    events = list(db.exec(select(AuditEvent)).all())
    assert len(events) == 1
    assert events[0].event_type == "identity.resource_grant.changed"
    assert events[0].resource_type == "knowledge"
    assert events[0].resource_id == "kb-audit"
    assert events[0].subject_user_id == "user-audit"
    assert events[0].operation == "grant"
