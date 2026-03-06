""" test_concurrent_tenant_isolation

Concurrent tenant isolation tests - verify isolation under concurrent access.
"""

import pytest
import asyncio
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.modules.appcenter.domain.models import App
from app.modules.appcenter.infra.repository import AppRepository


@pytest.fixture
def tenant1_ctx() -> RequestContext:
    """Create tenant 1 context."""
    return RequestContext(
        tenant_id="tenant_1",
        workspace_id="workspace_1",
        user_id="user_1",
        tenant_role="Owner",
        workspace_role="Owner",
    )


@pytest.fixture
def tenant2_ctx() -> RequestContext:
    """Create tenant 2 context."""
    return RequestContext(
        tenant_id="tenant_2",
        workspace_id="workspace_2",
        user_id="user_2",
        tenant_role="Owner",
        workspace_role="Owner",
    )


@pytest.mark.asyncio
async def test_concurrent_create_isolation(db: Session, tenant1_ctx: RequestContext, tenant2_ctx: RequestContext):
    """Test concurrent creation maintains tenant isolation."""

    async def create_app(tenant_ctx: RequestContext, name: str) -> App:
        """Create an app in a tenant."""
        repo = AppRepository(db, tenant_ctx)
        app = App(
            name=name,
            tenant_id=tenant_ctx.tenant_id,
            workspace_id=tenant_ctx.workspace_id,
            type="WORKFLOW",
            status="active",
            visibility="private",
        )
        return repo.create(app)

    # Create apps concurrently in different tenants
    app1_task = asyncio.create_task(create_app(tenant1_ctx, "App T1"))
    app2_task = asyncio.create_task(create_app(tenant2_ctx, "App T2"))

    app1, app2 = await asyncio.gather(app1_task, app2_task)

    # Verify apps are created in correct tenants
    assert app1.tenant_id == tenant1_ctx.tenant_id
    assert app2.tenant_id == tenant2_ctx.tenant_id

    # Verify tenant 1 can't see tenant 2's app
    repo1 = AppRepository(db, tenant1_ctx)
    fetched_app2 = repo1.get_by_id(app2.id)
    assert fetched_app2 is None

    # Verify tenant 2 can't see tenant 1's app
    repo2 = AppRepository(db, tenant2_ctx)
    fetched_app1 = repo2.get_by_id(app1.id)
    assert fetched_app1 is None


@pytest.mark.asyncio
async def test_concurrent_list_isolation(db: Session, tenant1_ctx: RequestContext, tenant2_ctx: RequestContext):
    """Test concurrent list operations maintain isolation."""

    # Create multiple apps in tenant 1
    repo1 = AppRepository(db, tenant1_ctx)
    for i in range(5):
        app = App(
            name=f"App T1-{i}",
            tenant_id=tenant1_ctx.tenant_id,
            workspace_id=tenant1_ctx.workspace_id,
            type="WORKFLOW",
            status="active",
            visibility="private",
        )
        repo1.create(app)

    # Create multiple apps in tenant 2
    repo2 = AppRepository(db, tenant2_ctx)
    for i in range(3):
        app = App(
            name=f"App T2-{i}",
            tenant_id=tenant2_ctx.tenant_id,
            workspace_id=tenant2_ctx.workspace_id,
            type="WORKFLOW",
            status="active",
            visibility="private",
        )
        repo2.create(app)

    # List apps concurrently
    async def list_apps(repo: AppRepository):
        return repo.list(page_size=100)

    list1_task = asyncio.create_task(list_apps(repo1))
    list2_task = asyncio.create_task(list_apps(repo2))

    result1, result2 = await asyncio.gather(list1_task, list2_task)

    # Verify correct counts
    assert len(result1.items) == 5
    assert len(result2.items) == 3

    # Verify no cross-tenant contamination
    tenant1_ids = {app.id for app in result1.items}
    tenant2_ids = {app.id for app in result2.items}
    assert tenant1_ids.isdisjoint(tenant2_ids)


def test_bulk_operation_isolation(db: Session, tenant1_ctx: RequestContext, tenant2_ctx: RequestContext):
    """Test bulk operations maintain tenant isolation."""
    # Create apps in tenant 1
    repo1 = AppRepository(db, tenant1_ctx)
    tenant1_apps = []
    for i in range(10):
        app = App(
            name=f"Bulk App T1-{i}",
            tenant_id=tenant1_ctx.tenant_id,
            workspace_id=tenant1_ctx.workspace_id,
            type="WORKFLOW",
            status="active",
            visibility="private",
        )
        tenant1_apps.append(repo1.create(app))

    # Create apps in tenant 2
    repo2 = AppRepository(db, tenant2_ctx)
    tenant2_apps = []
    for i in range(5):
        app = App(
            name=f"Bulk App T2-{i}",
            tenant_id=tenant2_ctx.tenant_id,
            workspace_id=tenant2_ctx.workspace_id,
            type="WORKFLOW",
            status="active",
            visibility="private",
        )
        tenant2_apps.append(repo2.create(app))

    # Verify tenant 1 sees only its apps
    all_tenant1 = repo1.list(page_size=100)
    assert len(all_tenant1.items) == 10
    for app in all_tenant1.items:
        assert app.tenant_id == tenant1_ctx.tenant_id

    # Verify tenant 2 sees only its apps
    all_tenant2 = repo2.list(page_size=100)
    assert len(all_tenant2.items) == 5
    for app in all_tenant2.items:
        assert app.tenant_id == tenant2_ctx.tenant_id
