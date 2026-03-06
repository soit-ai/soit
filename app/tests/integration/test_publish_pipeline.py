"""test_publish_pipeline

Integration tests for app publish pipeline.
"""

import pytest
from sqlalchemy import select

from app.kernel.contracts.context import RequestContext
from app.modules.appcenter.application.publish_service import AppPublishService
from app.modules.appcenter.domain.models import App, AppVersion, AppComponent, AppComponentEdge, AppVersionRef


@pytest.mark.asyncio
async def test_publish_builds_projections(db, tenant1_ctx: RequestContext):
    app = App(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        type="WORKFLOW",
        status="active",
        visibility="private",
        name="publish-test",
        description="publish test",
        created_by=tenant1_ctx.user_id,
    )
    db.add(app)
    db.commit()
    db.refresh(app)

    spec = {
        "name": "publish-test",
        "inputs_schema": {},
        "outputs_schema": {},
        "graph": {
            "nodes": [
                {"id": "tool1", "type": "tool", "params": {"tool_ref": "tool:http:demo"}},
                {"id": "out1", "type": "output", "params": {"value": "{{ steps.tool1.output.result }}"}},
            ],
            "edges": [{"id": "e1", "from": "tool1", "to": "out1"}],
        },
    }
    version = AppVersion(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        app_id=app.id,
        version=1,
        status="draft",
        spec_schema="workflow.v1",
        spec_json=spec,
        created_by=tenant1_ctx.user_id,
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    service = AppPublishService(db, tenant1_ctx)
    published = service.publish(app.id, version.id)

    assert published.status == "published"
    assert published.checksum
    db.refresh(app)
    assert app.current_version_id == published.id

    components = db.exec(
        select(AppComponent).where(AppComponent.app_version_id == published.id)
    ).scalars().all()
    edges = db.exec(
        select(AppComponentEdge).where(AppComponentEdge.app_version_id == published.id)
    ).scalars().all()
    refs = db.exec(
        select(AppVersionRef).where(AppVersionRef.app_version_id == published.id)
    ).scalars().all()

    assert len(components) == 2
    assert len(edges) == 1
    assert any(ref.ref_type == "tool" for ref in refs)
