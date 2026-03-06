"""test_agent_publish_and_execute

Integration tests for agent publish pipeline and runtime execution.
"""

import asyncio
import pytest
from sqlalchemy import select

from app.kernel.contracts.context import RequestContext
from app.modules.appcenter.application.publish_service import AppPublishService
from app.modules.appcenter.runtime.router import AppRuntimeRouter
from app.modules.appcenter.domain.models import App, AppVersion, AppVersionRef


@pytest.mark.asyncio
async def test_publish_agent_builds_refs(db, tenant1_ctx: RequestContext):
    publish_service = AppPublishService(db, tenant1_ctx)

    agent_app = App(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        type="AGENT",
        status="active",
        visibility="private",
        name="agent-app",
        description="agent",
        created_by=tenant1_ctx.user_id,
    )
    db.add(agent_app)
    db.commit()
    db.refresh(agent_app)

    agent_spec = {
        "runtime": "agent_runtime_v1",
        "model": {"ref_key": "model:openai:gpt-4"},
        "tools": {"allowlist": ["tool:http:demo"], "configs": {}},
        "rag": {"datasets": ["ds:dataset_1"]},
    }
    agent_version = AppVersion(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        app_id=agent_app.id,
        version=1,
        status="draft",
        spec_schema="agent.v1",
        spec_json=agent_spec,
        created_by=tenant1_ctx.user_id,
    )
    db.add(agent_version)
    db.commit()
    db.refresh(agent_version)
    publish_service.publish(agent_app.id, agent_version.id)

    refs = db.exec(
        select(AppVersionRef).where(AppVersionRef.app_version_id == agent_version.id)
    ).scalars().all()
    assert any(ref.ref_type == "model" for ref in refs)
    assert any(ref.ref_type == "tool" for ref in refs)
    assert any(ref.ref_type == "dataset" for ref in refs)


def test_runtime_router_executes_agent(db, tenant1_ctx: RequestContext):
    router = AppRuntimeRouter(db, tenant1_ctx)

    agent_app = App(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        type="AGENT",
        status="active",
        visibility="private",
        name="agent-exec",
        description="agent",
        created_by=tenant1_ctx.user_id,
    )
    db.add(agent_app)
    db.commit()
    db.refresh(agent_app)

    agent_spec = {
        "runtime": "agent_runtime_v1",
        "model": {"ref_key": "model:openai:gpt-4"},
        "tools": {"allowlist": []},
        "limits": {"max_iterations": 2},
    }
    agent_version = AppVersion(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        app_id=agent_app.id,
        version=1,
        status="published",
        spec_schema="agent.v1",
        spec_json=agent_spec,
        created_by=tenant1_ctx.user_id,
    )
    db.add(agent_version)
    db.commit()
    db.refresh(agent_version)
    agent_app.current_version_id = agent_version.id
    db.commit()

    result = asyncio.run(
        router.execute(
            app_id=agent_app.id,
            inputs={"messages": [{"role": "user", "content": "hello agent"}]},
        )
    )
    assert result.get("run_id")
    assert "output" in (result.get("output") or {})
