"""An agent exported as a file imports back as the same agent with the same version spec."""

from __future__ import annotations

import pytest
from fastapi import status

from app.api.v1.agent.dependencies import get_agent_application_service
from app.kernel.ports.llm.interface import ChatResponse, LLMPort
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.main import app
from app.modules.agent.application.application_service import AgentApplicationService

VERSION = {
    "system_prompt": "Answer briefly.",
    "temperature": 0.2,
    "max_iterations": 3,
    "max_runtime_seconds": 60,
    "max_cost": 2.0,
    "cost_currency": "USD",
    "bindings": {"model_ref": "model:test:chat", "tool_refs": ["tool:echo"]},
    "verify": True,
}


class _Idle(LLMPort):
    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        return ChatResponse(text="", tokens_prompt=0, tokens_completion=0, finish_reason="stop")

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError


class _Tools(ToolPort):
    async def invoke(self, tool_ref, parameters, **kwargs):
        return ToolResponse(result={})


@pytest.fixture
def agent_service(async_db, ctx):
    async def build() -> AgentApplicationService:
        return AgentApplicationService(db=async_db, ctx=ctx, llm_port=_Idle(), tool_port=_Tools())

    app.dependency_overrides[get_agent_application_service] = build
    yield
    app.dependency_overrides.pop(get_agent_application_service, None)


async def _agent_with_version(async_client) -> tuple[str, dict]:
    agent = await async_client.post(
        "/api/v1/agents",
        json={"name": "support-triage", "description": "Triage", "category": "support", "tags": ["a", "b"]},
    )
    agent_id = agent.json()["data"]["id"]
    version = await async_client.post(f"/api/v1/agents/{agent_id}/versions", json=VERSION)
    assert version.status_code == status.HTTP_201_CREATED, version.text
    return agent_id, version.json()["data"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("agent_service")
async def test_an_agent_exports_and_imports_with_the_same_spec(async_client) -> None:
    agent_id, original = await _agent_with_version(async_client)

    exported = await async_client.get(f"/api/v1/agents/{agent_id}/export")

    assert exported.status_code == status.HTTP_200_OK, exported.text
    document = exported.json()["data"]
    assert document["soit"] == "agent/v1"
    assert document["agent"] == {
        "name": "support-triage",
        "description": "Triage",
        "visibility": "private",
        "category": "support",
        "icon_url": None,
        "tags": ["a", "b"],
    }
    assert document["version"]["bindings"] == {
        "model_ref": "model:test:chat",
        "knowledge_refs": [],
        "tool_refs": ["tool:echo"],
        "workflow_refs": [],
        "skill_refs": [],
    }
    assert "id" not in document["version"]

    document["agent"]["name"] = "support-triage-copy"
    imported = await async_client.post("/api/v1/agents/import", json=document)

    assert imported.status_code == status.HTTP_201_CREATED, imported.text
    body = imported.json()["data"]
    assert body["agent"]["name"] == "support-triage-copy"
    assert body["agent"]["id"] != agent_id
    assert body["version"]["agent_id"] == body["agent"]["id"]
    # The same specification, byte for byte.
    assert body["version"]["checksum"] == original["checksum"]
    assert body["version"]["spec_json"] == original["spec_json"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("agent_service")
async def test_an_agent_without_a_version_exports_none_and_imports_as_one(async_client) -> None:
    agent_id = (await async_client.post("/api/v1/agents", json={"name": "bare"})).json()["data"]["id"]

    document = (await async_client.get(f"/api/v1/agents/{agent_id}/export")).json()["data"]
    assert document["version"] is None

    document["agent"]["name"] = "bare-copy"
    imported = await async_client.post("/api/v1/agents/import", json=document)

    assert imported.status_code == status.HTTP_201_CREATED, imported.text
    assert imported.json()["data"]["version"] is None


@pytest.mark.asyncio
@pytest.mark.usefixtures("agent_service")
async def test_a_file_with_an_unknown_key_or_a_taken_name_is_refused(async_client) -> None:
    agent_id, _ = await _agent_with_version(async_client)
    document = (await async_client.get(f"/api/v1/agents/{agent_id}/export")).json()["data"]

    taken = await async_client.post("/api/v1/agents/import", json=document)
    assert taken.status_code == status.HTTP_400_BAD_REQUEST, taken.text

    document["agent"]["name"] = "fresh"
    document["version"]["id"] = "ver_1"
    unknown = await async_client.post("/api/v1/agents/import", json=document)
    assert unknown.status_code == status.HTTP_400_BAD_REQUEST, unknown.text
    assert unknown.json()["code"] == "VALIDATION_ERROR"
    assert unknown.json()["details"]["errors"][0]["field"] == "body.version.id"
