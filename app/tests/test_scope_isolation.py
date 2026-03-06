""" test_scope_isolation

Scope isolation tests - verify tenant/workspace isolation.
"""

import pytest
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.modules.appcenter.domain.models import App
from app.modules.appcenter.infra.repository import AppRepository
from app.modules.dataset.domain.models import Dataset
from app.modules.dataset.infra.repository import DatasetRepository


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


def test_workflow_scope_isolation(db: Session, tenant1_ctx: RequestContext, tenant2_ctx: RequestContext):
    """Test that workflows are isolated by tenant/workspace."""
    # Create workflow app in tenant 1
    repo1 = AppRepository(db, tenant1_ctx)
    workflow1 = App(
        name="Workflow 1",
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        type="WORKFLOW",
        status="active",
        visibility="private",
    )
    workflow1 = repo1.create(workflow1)
    
    # Try to access from tenant 2
    repo2 = AppRepository(db, tenant2_ctx)
    workflow2 = repo2.get_by_id(workflow1.id)
    
    # Should not be accessible
    assert workflow2 is None
    
    # List workflows in tenant 2 should not include tenant 1's workflow
    workflows = repo2.list(page_size=100)
    assert workflow1.id not in [w.id for w in workflows.items]


def test_dataset_scope_isolation(db: Session, tenant1_ctx: RequestContext, tenant2_ctx: RequestContext):
    """Test that datasets are isolated by tenant/workspace."""
    # Create dataset in tenant 1
    repo1 = DatasetRepository(db, tenant1_ctx)
    dataset1 = Dataset(
        name="Dataset 1",
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
    )
    dataset1 = repo1.create(dataset1)
    
    # Try to access from tenant 2
    repo2 = DatasetRepository(db, tenant2_ctx)
    dataset2 = repo2.get_by_id(dataset1.id)
    
    # Should not be accessible
    assert dataset2 is None
    
    # List datasets in tenant 2 should not include tenant 1's dataset
    datasets = repo2.list(limit=100, offset=0)
    assert dataset1.id not in [d.id for d in datasets]


def test_cross_workspace_isolation(db: Session, tenant1_ctx: RequestContext):
    """Test that resources are isolated by workspace within same tenant."""
    # Create workspace 1 context
    ctx1 = RequestContext(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id="workspace_1",
        user_id=tenant1_ctx.user_id,
        tenant_role="Owner",
        workspace_role="Owner",
    )
    
    # Create workspace 2 context (same tenant)
    ctx2 = RequestContext(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id="workspace_2",
        user_id=tenant1_ctx.user_id,
        tenant_role="Owner",
        workspace_role="Owner",
    )
    
    # Create workflow app in workspace 1
    repo1 = AppRepository(db, ctx1)
    workflow1 = App(
        name="Workflow 1",
        tenant_id=ctx1.tenant_id,
        workspace_id=ctx1.workspace_id,
        type="WORKFLOW",
        status="active",
        visibility="private",
    )
    workflow1 = repo1.create(workflow1)
    
    # Try to access from workspace 2
    repo2 = AppRepository(db, ctx2)
    workflow2 = repo2.get_by_id(workflow1.id)
    
    # Should not be accessible (different workspace)
    assert workflow2 is None
