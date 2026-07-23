from __future__ import annotations

from typing import Annotated

import pytest
from fastapi import Depends, status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlmodel import Session as SQLModelSession

from app.api.v1.agent.dependencies import get_agent_application_service
from app.infra.db.session import get_db
from app.infra.db.transaction import SQLAlchemyUnitOfWork
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import ChatResponse, LLMPort
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.middleware.auth import get_current_context
from app.modules.agent.application.application_service import AgentApplicationService


class JourneyLLMPort(LLMPort):
    """Deterministic model boundary for the no-seed product journey."""

    async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
        return ChatResponse(
            text="The new workspace answer is grounded in its knowledge base.",
            tokens_prompt=8,
            tokens_completion=10,
            finish_reason="stop",
        )

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError


class JourneyToolPort(ToolPort):
    async def invoke(self, tool_ref, parameters, **kwargs):
        return ToolResponse(result={"tool_ref": tool_ref, "parameters": parameters})


@pytest.fixture
def empty_workspace_client(db, monkeypatch):
    from app import middleware
    from app.main import app
    from app.modules.identity.infra import workspace_access
    from app.settings.settings import settings

    def override_get_db():
        with SQLAlchemyUnitOfWork(db):
            yield db

    def scoped_session():
        return SQLModelSession(bind=db.get_bind(), expire_on_commit=False)

    previous_registration = settings.allow_public_registration
    previous_ingest_worker = settings.knowledge_ingest_worker_enabled
    previous_dispatcher = settings.outbox_dispatcher_enabled
    settings.allow_public_registration = True
    settings.knowledge_ingest_worker_enabled = False
    settings.outbox_dispatcher_enabled = False
    monkeypatch.setattr(workspace_access, "get_db_sync", scoped_session)
    monkeypatch.setattr(middleware.auth, "_context_resolver", None)
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client
    finally:
        settings.allow_public_registration = previous_registration
        settings.knowledge_ingest_worker_enabled = previous_ingest_worker
        settings.outbox_dispatcher_enabled = previous_dispatcher
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_agent_application_service, None)


def test_new_workspace_completes_governed_main_journeys_without_seed_data(
    empty_workspace_client: TestClient,
    monkeypatch,
):
    from app.main import app
    from app.modules.knowledge.runtime import tool_entrypoint

    client = empty_workspace_client
    register_payload = {
        "email": "release-journey@example.com",
        "password": "ReleaseJourney123!",
        "name": "Release Journey",
    }
    registered = client.post(
        "/api/v1/register?tenant_name=Release%20Journey",
        json=register_payload,
    )
    assert registered.status_code == status.HTTP_200_OK
    workspace_id = registered.json()["data"]["workspace_id"]

    logged_in = client.post(
        "/api/v1/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert logged_in.status_code == status.HTTP_200_OK
    token = logged_in.json()["data"]["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-Id": workspace_id,
    }
    current_user = client.get("/api/v1/me", headers=headers)
    assert current_user.status_code == status.HTTP_200_OK
    user_data = current_user.json()["data"]
    assert user_data["email"] == register_payload["email"]
    assert user_data["workspace_id"] == workspace_id

    knowledge_response = client.post(
        "/api/v1/knowledge",
        headers=headers,
        json={
            "name": "Release Support Knowledge",
            "description": "Created from an empty registered workspace",
            "knowledge_type": "document",
            "visibility": "workspace",
        },
    )
    assert knowledge_response.status_code == status.HTTP_201_CREATED
    knowledge = knowledge_response.json()["data"]
    assert knowledge["workspace_id"] == workspace_id

    async def query_new_workspace_knowledge(**kwargs):
        assert kwargs["knowledge_id"] == knowledge["id"]
        return {
            "results": [
                {
                    "chunk_id": "journey-chunk",
                    "document_id": "journey-document",
                    "score": 0.99,
                    "text": "Release support knowledge is available.",
                    "metadata": {},
                }
            ],
            "total": 1,
            "citations": [
                {
                    "chunk_id": "journey-chunk",
                    "document_id": "journey-document",
                    "rank": 1,
                    "score": 0.99,
                    "knowledge_id": knowledge["id"],
                    "title": "Release Support Knowledge",
                    "snippet": "Release support knowledge is available.",
                }
            ],
        }

    monkeypatch.setattr(tool_entrypoint, "knowledge_query", query_new_workspace_knowledge)

    async def override_agent_service(
        ctx: Annotated[RequestContext, Depends(get_current_context)],
        session: Annotated[Session, Depends(get_db)],
    ) -> AgentApplicationService:
        return AgentApplicationService(
            db=session,
            ctx=ctx,
            llm_port=JourneyLLMPort(),
            tool_port=JourneyToolPort(),
            memory_service=None,
        )

    app.dependency_overrides[get_agent_application_service] = override_agent_service

    agent_response = client.post(
        "/api/v1/agents",
        headers=headers,
        json={
            "name": "Release Support Agent",
            "description": "Created from an empty registered workspace",
            "visibility": "private",
        },
    )
    assert agent_response.status_code == status.HTTP_201_CREATED
    agent = agent_response.json()["data"]

    agent_version_response = client.post(
        f"/api/v1/agents/{agent['id']}/versions",
        headers=headers,
        json={
            "system_prompt": "Answer with the bound workspace knowledge.",
            "bindings": {
                "model_ref": "model:test:release-journey",
                "knowledge_refs": [f"knowledge:{knowledge['id']}"],
            },
            "verify": False,
        },
    )
    assert agent_version_response.status_code == status.HTTP_201_CREATED
    agent_version_id = agent_version_response.json()["data"]["id"]
    published_agent = client.post(
        f"/api/v1/agents/{agent['id']}/publish",
        headers=headers,
        json={"version_id": agent_version_id},
    )
    assert published_agent.status_code == status.HTTP_200_OK
    assert published_agent.json()["data"]["published_version_id"] == agent_version_id

    chat_response = client.post(
        f"/api/v1/agents/{agent['id']}/execute",
        headers=headers,
        json={"input": "What knowledge is available?"},
    )
    assert chat_response.status_code == status.HTTP_200_OK
    chat = chat_response.json()["data"]
    assert chat["output"] == "The new workspace answer is grounded in its knowledge base."
    assert chat["citations"][0]["knowledge_id"] == knowledge["id"]

    thread_response = client.get(f"/api/v1/threads/{chat['thread_id']}", headers=headers)
    assert thread_response.status_code == status.HTTP_200_OK
    thread_messages = thread_response.json()["data"]["messages"]
    assert [message["role"] for message in thread_messages] == ["user", "assistant"]

    replay_response = client.get(f"/api/v1/observe/runs/{chat['run_id']}/replay", headers=headers)
    assert replay_response.status_code == status.HTTP_200_OK
    replay = replay_response.json()["data"]
    assert replay["run"]["id"] == chat["run_id"]
    assert replay["run"]["status"] == "succeeded"

    workflow_response = client.post(
        "/api/v1/workflows",
        headers=headers,
        json={"name": "Release Journey Workflow", "description": "No-seed preview and publish"},
    )
    assert workflow_response.status_code == status.HTTP_201_CREATED
    workflow = workflow_response.json()["data"]
    workflow_version_response = client.post(
        f"/api/v1/workflows/{workflow['id']}/versions",
        headers=headers,
        json={
            "graph_json": {
                "name": "release-journey-flow",
                "inputs_schema": {"type": "object", "properties": {"value": {"type": "string"}}},
                "outputs_schema": {"type": "object", "properties": {"value": {"type": "string"}}},
                "graph": {
                    "nodes": [
                        {
                            "id": "set_value",
                            "type": "set_var",
                            "params": {"key": "value", "value": "{{ inputs.value }}"},
                        },
                        {
                            "id": "output_value",
                            "type": "output",
                            "params": {"value": "{{ steps.set_value.output.value }}"},
                        },
                    ],
                    "edges": [{"id": "edge-1", "from": "set_value", "to": "output_value"}],
                },
            }
        },
    )
    assert workflow_version_response.status_code == status.HTTP_201_CREATED
    workflow_version_id = workflow_version_response.json()["data"]["id"]

    preview_response = client.post(
        f"/api/v1/workflows/{workflow['id']}/versions/{workflow_version_id}/preview",
        headers=headers,
        json={"inputs": {"value": "preview-ok"}},
    )
    assert preview_response.status_code == status.HTTP_200_OK
    assert preview_response.json()["data"]["output"] == {"value": "preview-ok"}

    published_workflow = client.post(
        f"/api/v1/workflows/{workflow['id']}/publish",
        headers=headers,
        json={"version_id": workflow_version_id},
    )
    assert published_workflow.status_code == status.HTTP_200_OK
    assert published_workflow.json()["data"]["published_version_id"] == workflow_version_id

    workflow_run = client.post(
        f"/api/v1/workflows/{workflow['id']}/execute",
        headers=headers,
        json={"value": "published-ok"},
    )
    assert workflow_run.status_code == status.HTTP_200_OK
    assert workflow_run.json()["data"]["output"] == {"value": "published-ok"}
