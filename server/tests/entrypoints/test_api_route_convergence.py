"""API v1 public route convergence contracts."""

from types import SimpleNamespace

import pytest
from sqlalchemy import and_, func, select

from app.modules.agent.domain.models import Agent
from app.modules.knowledge.domain.models import KnowledgeDocument
from app.modules.modelhub.domain.models import Provider, ProviderModel
from scripts.bootstrap_enterprise_mvp import DEMO_AGENT_NAME, bootstrap_enterprise_mvp
from scripts.smoke import run_all as smoke_run_all


def _count_value(value):
    if isinstance(value, tuple):
        return value[0]
    try:
        return value[0]
    except Exception:
        return value


def test_legacy_public_routes_are_absent_from_openapi(client):
    schema = client.get("/api/v1/openapi.json").json()
    paths = set(schema["paths"])

    removed_prefixes = (
        "/api/v1/chat",
        "/api/v1/memory",
        "/api/v1/mcp",
        "/api/v1/skills",
        "/api/v1/sse",
        "/api/v1/ws",
    )
    for prefix in removed_prefixes:
        assert not any(path == prefix or path.startswith(f"{prefix}/") for path in paths)


def test_enterprise_mvp_demo_uses_converged_public_routes(client):
    schema = client.get("/api/v1/openapi.json").json()
    paths = set(schema["paths"])

    required_paths = {
        "/api/v1/agents",
        "/api/v1/agents/{agent_id}/versions",
        "/api/v1/agents/{agent_id}/publish",
        "/api/v1/knowledge",
        "/api/v1/workflows",
        "/api/v1/workflows/{workflow_id}/publish",
        "/api/v1/observe/dashboard",
        "/api/v1/runs/{run_id}",
    }
    assert required_paths.issubset(paths)


@pytest.mark.asyncio
async def test_enterprise_mvp_bootstrap_is_idempotent(db):
    args = SimpleNamespace(
        email="enterprise-demo@example.com",
        password="changeme123",
        name="Enterprise Demo",
        tenant_name="enterprise-demo",
        workspace_name="default",
    )

    first = await bootstrap_enterprise_mvp(db, args)
    second = await bootstrap_enterprise_mvp(db, args)

    assert second.agent_id == first.agent_id
    assert second.agent_version_id == first.agent_version_id
    assert second.knowledge_id == first.knowledge_id
    assert second.document_id == first.document_id
    assert second.workflow_id == first.workflow_id

    agent_count = db.exec(
        select(func.count(Agent.id)).where(
            and_(
                Agent.tenant_id == first.tenant_id,
                Agent.workspace_id == first.workspace_id,
                Agent.name == DEMO_AGENT_NAME,
            )
        )
    ).one()
    document_count = db.exec(
        select(func.count(KnowledgeDocument.id)).where(
            and_(
                KnowledgeDocument.tenant_id == first.tenant_id,
                KnowledgeDocument.workspace_id == first.workspace_id,
                KnowledgeDocument.knowledge_id == first.knowledge_id,
                KnowledgeDocument.doc_key == "refund-policy.md",
            )
        )
    ).one()
    provider_model_count = db.exec(
        select(func.count(ProviderModel.id)).where(
            and_(
                ProviderModel.tenant_id == first.tenant_id,
                ProviderModel.workspace_id == first.workspace_id,
                ProviderModel.provider_kind == "test",
            )
        )
    ).one()
    provider_row = db.exec(
        select(Provider).where(
            and_(
                Provider.tenant_id == first.tenant_id,
                Provider.workspace_id == first.workspace_id,
                Provider.name == "Enterprise MVP Stub",
            )
        )
    ).one()
    provider = _count_value(provider_row)
    assert _count_value(agent_count) == 1
    assert _count_value(document_count) == 1
    assert provider.slug == "enterprise-mvp-stub"
    assert _count_value(provider_model_count) == 3


@pytest.mark.asyncio
async def test_enterprise_mvp_bootstrap_uses_workspace_scoped_demo_ids(db):
    args_default = SimpleNamespace(
        email="enterprise-demo-scope@example.com",
        password="changeme123",
        name="Enterprise Demo",
        tenant_name="enterprise-demo-scope",
        workspace_name="default",
    )
    args_second_workspace = SimpleNamespace(
        email="enterprise-demo-scope@example.com",
        password="changeme123",
        name="Enterprise Demo",
        tenant_name="enterprise-demo-scope",
        workspace_name="secondary",
    )

    first = await bootstrap_enterprise_mvp(db, args_default)
    second = await bootstrap_enterprise_mvp(db, args_second_workspace)
    second_repeat = await bootstrap_enterprise_mvp(db, args_second_workspace)

    assert second.workspace_id != first.workspace_id
    assert second.knowledge_id != first.knowledge_id
    assert second.document_id != first.document_id
    assert second_repeat.knowledge_id == second.knowledge_id
    assert second_repeat.document_id == second.document_id


@pytest.mark.asyncio
async def test_enterprise_mvp_bootstrap_allows_new_user_in_existing_tenant(db):
    owner_args = SimpleNamespace(
        email="enterprise-demo-owner@example.com",
        password="changeme123",
        name="Enterprise Demo Owner",
        tenant_name="enterprise-demo-shared",
        workspace_name="default",
    )
    reviewer_args = SimpleNamespace(
        email="enterprise-demo-reviewer@example.com",
        password="changeme123",
        name="Enterprise Demo Reviewer",
        tenant_name="enterprise-demo-shared",
        workspace_name="default",
    )

    owner = await bootstrap_enterprise_mvp(db, owner_args)
    reviewer = await bootstrap_enterprise_mvp(db, reviewer_args)

    assert reviewer.tenant_id == owner.tenant_id
    assert reviewer.workspace_id == owner.workspace_id
    assert reviewer.agent_id == owner.agent_id


def test_enterprise_mvp_smoke_bootstrap_uses_requested_admin(monkeypatch):
    commands = []

    def fake_run(command, cwd, check):
        _ = (cwd, check)
        commands.append(command)
        return SimpleNamespace(returncode=0)

    args = SimpleNamespace(
        admin_email="admin@example.com",
        admin_password="12345678",
    )
    monkeypatch.setattr(smoke_run_all.subprocess, "run", fake_run)

    failures = smoke_run_all._run_enterprise_mvp_smoke(args)

    assert failures == 0
    bootstrap_command = commands[0]
    assert "--email" in bootstrap_command
    assert bootstrap_command[bootstrap_command.index("--email") + 1] == "admin@example.com"
    assert "--password" in bootstrap_command
    assert bootstrap_command[bootstrap_command.index("--password") + 1] == "12345678"


def test_smoke_workflow_version_request_omits_created_by(monkeypatch):
    requests = []

    def fake_request(_ctx, method, path, **kwargs):
        requests.append((method, path, kwargs))
        if path == "/workflows":
            return {"id": "wf-smoke"}
        if path == "/workflows/wf-smoke/versions":
            return {"id": "wfv-smoke"}
        if path == "/workflows/wf-smoke/execute":
            return {"run_id": "run-smoke"}
        return {}

    monkeypatch.setattr(smoke_run_all, "_request", fake_request)
    ctx = smoke_run_all.SmokeContext(
        base_url="http://testserver/api/v1",
        token="test-token",
        tenant_id="test-tenant",
        workspace_id="test-workspace",
        user_id="test-user",
        strict=False,
        timeout_seconds=30,
        poll_interval=0.01,
        embedding_model_ref="model:test:embedding",
        response_model_ref="model:test:chat",
        inline_ingest_worker=False,
    )

    smoke_run_all.demo_workflow(ctx)

    version_request = next(item for item in requests if item[1] == "/workflows/wf-smoke/versions")
    payload = version_request[2]["json"]
    assert "graph_json" in payload
    assert "created_by" not in payload


def test_smoke_llm_gate_allows_test_model_refs_without_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert smoke_run_all._ensure_llm_ready(False, "stub demo", "model:test:agent") is True
