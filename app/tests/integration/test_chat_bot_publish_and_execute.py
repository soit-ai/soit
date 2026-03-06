"""test_chat_bot_publish_and_execute

Integration tests for chat/bot publish pipeline and runtime execution.
"""

import asyncio
import pytest
from sqlalchemy import select

from app.kernel.contracts.context import RequestContext
from app.modules.appcenter.application.publish_service import AppPublishService
from app.modules.appcenter.runtime.router import AppRuntimeRouter
from app.modules.appcenter.domain.models import App, AppVersion, AppVersionRef


@pytest.mark.asyncio
async def test_publish_chat_and_bot_build_refs(db, tenant1_ctx: RequestContext):
    publish_service = AppPublishService(db, tenant1_ctx)

    chat_app = App(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        type="CHAT",
        status="active",
        visibility="private",
        name="chat-app",
        description="chat",
        created_by=tenant1_ctx.user_id,
    )
    db.add(chat_app)
    db.commit()
    db.refresh(chat_app)

    chat_spec = {
        "runtime": "chat_runtime_v1",
        "model": {"ref_key": "model:openai:gpt-4"},
        "tools": {"allowlist": ["tool:http:demo"], "configs": {}},
        "rag": {"datasets": ["ds:dataset_1"]},
    }
    chat_version = AppVersion(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        app_id=chat_app.id,
        version=1,
        status="draft",
        spec_schema="chat.v1",
        spec_json=chat_spec,
        created_by=tenant1_ctx.user_id,
    )
    db.add(chat_version)
    db.commit()
    db.refresh(chat_version)
    publish_service.publish(chat_app.id, chat_version.id)

    refs = db.exec(
        select(AppVersionRef).where(AppVersionRef.app_version_id == chat_version.id)
    ).scalars().all()
    assert any(ref.ref_type == "model" for ref in refs)
    assert any(ref.ref_type == "tool" for ref in refs)
    assert any(ref.ref_type == "dataset" for ref in refs)

    bot_app = App(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        type="BOT",
        status="active",
        visibility="private",
        name="bot-app",
        description="bot",
        created_by=tenant1_ctx.user_id,
    )
    db.add(bot_app)
    db.commit()
    db.refresh(bot_app)

    bot_spec = {
        "runtime": "bot_runtime_v1",
        "chat": chat_spec,
        "triggers": {"webhook": {"secret_ref": "secret:webhook"}},
    }
    bot_version = AppVersion(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        app_id=bot_app.id,
        version=1,
        status="draft",
        spec_schema="bot.v1",
        spec_json=bot_spec,
        created_by=tenant1_ctx.user_id,
    )
    db.add(bot_version)
    db.commit()
    db.refresh(bot_version)
    publish_service.publish(bot_app.id, bot_version.id)

    bot_refs = db.exec(
        select(AppVersionRef).where(AppVersionRef.app_version_id == bot_version.id)
    ).scalars().all()
    assert any(ref.ref_type == "model" for ref in bot_refs)
    assert any(ref.ref_type == "secret" for ref in bot_refs)


def test_runtime_router_executes_chat_and_bot(db, tenant1_ctx: RequestContext):
    router = AppRuntimeRouter(db, tenant1_ctx)

    chat_app = App(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        type="CHAT",
        status="active",
        visibility="private",
        name="chat-exec",
        description="chat",
        created_by=tenant1_ctx.user_id,
    )
    db.add(chat_app)
    db.commit()
    db.refresh(chat_app)

    chat_spec = {
        "runtime": "chat_runtime_v1",
        "model": {"ref_key": "model:openai:gpt-4"},
        "system_prompt": "You are helpful.",
    }
    chat_version = AppVersion(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        app_id=chat_app.id,
        version=1,
        status="published",
        spec_schema="chat.v1",
        spec_json=chat_spec,
        created_by=tenant1_ctx.user_id,
    )
    db.add(chat_version)
    db.commit()
    db.refresh(chat_version)
    chat_app.current_version_id = chat_version.id
    db.commit()

    chat_result = asyncio.run(
        router.execute(
            app_id=chat_app.id,
            inputs={"messages": [{"role": "user", "content": "hello"}]},
        )
    )
    assert chat_result.get("run_id")
    assert chat_result.get("output", {}).get("text") == "hello"

    bot_app = App(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        type="BOT",
        status="active",
        visibility="private",
        name="bot-exec",
        description="bot",
        created_by=tenant1_ctx.user_id,
    )
    db.add(bot_app)
    db.commit()
    db.refresh(bot_app)

    bot_spec = {
        "runtime": "bot_runtime_v1",
        "chat": chat_spec,
    }
    bot_version = AppVersion(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        app_id=bot_app.id,
        version=1,
        status="published",
        spec_schema="bot.v1",
        spec_json=bot_spec,
        created_by=tenant1_ctx.user_id,
    )
    db.add(bot_version)
    db.commit()
    db.refresh(bot_version)
    bot_app.current_version_id = bot_version.id
    db.commit()

    bot_result = asyncio.run(
        router.execute(
            app_id=bot_app.id,
            inputs={"messages": [{"role": "user", "content": "hi bot"}]},
        )
    )
    assert bot_result.get("run_id")
    assert bot_result.get("output", {}).get("text") == "hi bot"
