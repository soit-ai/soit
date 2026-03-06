"""test_appcenter_projection_queries

Unit tests for projection query APIs and impact analysis.
"""

import pytest

from app.modules.appcenter.application.service import AppService
from app.modules.appcenter.application.publish_service import AppPublishService
from app.modules.appcenter.application.schemas import AppCreate, AppVersionCreate
from app.modules.appcenter.infra.repository import (
    AppRepository,
    AppVersionRepository,
    AppMarketRepository,
    AppInstallationRepository,
)


def _build_service(db, ctx) -> AppService:
    return AppService(
        db=db,
        ctx=ctx,
        app_repo=AppRepository(db, ctx),
        app_version_repo=AppVersionRepository(db, ctx),
        app_market_repo=AppMarketRepository(db, ctx),
        app_installation_repo=AppInstallationRepository(db, ctx),
    )


@pytest.mark.asyncio
async def test_projection_queries_and_impact(db, tenant1_ctx):
    service = _build_service(db, tenant1_ctx)
    publish_service = AppPublishService(db, tenant1_ctx)

    app = await service.create_app(AppCreate(name="proj-app", description="projection"))
    version = await service.create_version(
        app.id,
        AppVersionCreate(
            spec_schema="workflow.v1",
            spec_json={
                "name": "proj-app",
                "inputs_schema": {},
                "outputs_schema": {},
                "graph": {
                    "nodes": [
                        {
                            "id": "tool1",
                            "type": "tool",
                            "params": {"tool_ref": "tool:http:demo"},
                        },
                        {
                            "id": "out1",
                            "type": "output",
                            "params": {"value": "{{ steps.tool1.output.result }}"},
                        },
                    ],
                    "edges": [{"id": "e1", "from": "tool1", "to": "out1"}],
                },
            },
            changelog="init",
        ),
    )
    publish_service.publish(app.id, version.id)

    components = await service.list_components(app.id, version.id)
    edges = await service.list_edges(app.id, version.id)
    refs = await service.list_refs(app.id, version.id)

    assert len(components) == 2
    assert len(edges) == 1
    assert any(ref.ref_type == "tool" for ref in refs)

    impact = await service.impact_refs(ref_type="tool", ref_key="tool:http:demo")
    assert version.id in impact
