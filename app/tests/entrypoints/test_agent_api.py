"""Entry-point tests for the Agent API."""

from fastapi import status

from app.api.v1.agent.dependencies import get_agent_application_service
from app.kernel.ports.llm.interface import ChatResponse, LLMPort
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.modules.agent.application.application_service import AgentApplicationService


class QueueLLMPort(LLMPort):
    """LLM stub returning queued JSON payloads."""

    def __init__(self, responses):
        self._responses = list(responses)

    async def chat(self, messages, model, temperature=None, max_tokens=None, **kwargs):
        return self._responses.pop(0)

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError


class StubToolPort(ToolPort):
    """Tool stub with deterministic success."""

    async def invoke(self, tool_ref, parameters, **kwargs):
        return ToolResponse(result={"tool_ref": tool_ref, "parameters": parameters})


def test_agent_api_create_publish_and_execute(client, db, ctx):
    from app.main import app

    async def _override_agent_application_service() -> AgentApplicationService:
        return AgentApplicationService(
            db=db,
            ctx=ctx,
            llm_port=QueueLLMPort(
                [
                    ChatResponse(
                        text='{"action":"respond","response":"api done"}',
                        tokens_prompt=1,
                        tokens_completion=1,
                        finish_reason="stop",
                    ),
                    ChatResponse(
                        text='{"ok": true, "reason": "ok"}',
                        tokens_prompt=1,
                        tokens_completion=1,
                        finish_reason="stop",
                    ),
                ]
            ),
            tool_port=StubToolPort(),
            memory_service=None,
        )

    app.dependency_overrides[get_agent_application_service] = _override_agent_application_service
    try:
        create_response = client.post(
            "/api/v1/agents",
            json={
                "name": "api-agent",
                "description": "Agent API test",
                "visibility": "private",
                "icon_url": "https://example.com/agent.png",
                "category": "ops",
                "is_public": True,
                "featured": True,
                "tags": ["api"],
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        created_agent = create_response.json()["data"]
        agent_id = created_agent["id"]
        assert created_agent["icon_url"] == "https://example.com/agent.png"
        assert created_agent["category"] == "ops"
        assert created_agent["is_public"] is True
        assert created_agent["featured"] is True
        assert created_agent["downloads_count"] == 0
        assert created_agent["reviews_count"] == 0

        version_response = client.post(
            f"/api/v1/agents/{agent_id}/versions",
            json={
                "system_prompt": "You are precise.",
                "model_ref": "model:test:primary",
                "knowledge_refs": ["knowledge:kb_support"],
                "tool_refs": ["tool:test:echo"],
                "verify": True,
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert version_response.status_code == status.HTTP_201_CREATED
        version_id = version_response.json()["data"]["id"]

        bindings_response = client.get(
            f"/api/v1/agents/{agent_id}/bindings",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert bindings_response.status_code == status.HTTP_200_OK
        binding_types = {item["binding_type"] for item in bindings_response.json()["data"]}
        assert "model" in binding_types
        assert "tool" in binding_types
        assert "knowledge" in binding_types

        publish_response = client.post(
            f"/api/v1/agents/{agent_id}/publish",
            json={"version_id": version_id},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert publish_response.status_code == status.HTTP_200_OK
        assert publish_response.json()["data"]["published_version_id"] == version_id
        assert publish_response.json()["data"]["published_at"] is not None

        execute_response = client.post(
            f"/api/v1/agents/{agent_id}/execute",
            json={
                "messages": [{"role": "user", "content": "Execute now"}],
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert execute_response.status_code == status.HTTP_200_OK
        payload = execute_response.json()["data"]
        assert payload["output"] == "api done"
        assert payload["response_id"].startswith("resp_")
        assert payload["thread_id"].startswith("thr_")
        assert payload["task_id"].startswith("task_")

        linked_response = client.get(
            f"/api/v1/responses/{payload['response_id']}",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert linked_response.status_code == status.HTTP_200_OK
        assert linked_response.json()["data"]["run_id"] == payload["run_id"]

        list_response = client.get(
            "/api/v1/agents",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert list_response.status_code == status.HTTP_200_OK
        assert len(list_response.json()["data"]["items"]) == 1
    finally:
        app.dependency_overrides.pop(get_agent_application_service, None)


def test_agent_api_tool_calls_appear_in_response_detail(client, db, ctx):
    from app.main import app

    async def _override_agent_application_service() -> AgentApplicationService:
        return AgentApplicationService(
            db=db,
            ctx=ctx,
            llm_port=QueueLLMPort(
                [
                    ChatResponse(
                        text='{"action":"tool","tool_ref":"tool:test:echo","parameters":{"value":"api hi"}}',
                        tokens_prompt=1,
                        tokens_completion=1,
                        finish_reason="stop",
                    ),
                    ChatResponse(
                        text='{"action":"respond","response":"api tool done"}',
                        tokens_prompt=1,
                        tokens_completion=1,
                        finish_reason="stop",
                    ),
                    ChatResponse(
                        text='{"ok": true, "reason": "ok"}',
                        tokens_prompt=1,
                        tokens_completion=1,
                        finish_reason="stop",
                    ),
                ]
            ),
            tool_port=StubToolPort(),
            memory_service=None,
        )

    app.dependency_overrides[get_agent_application_service] = _override_agent_application_service
    try:
        create_response = client.post(
            "/api/v1/agents",
            json={
                "name": "api-agent-tools",
                "description": "Agent API tool detail test",
                "visibility": "private",
                "category": "ops",
                "tags": ["api"],
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        agent_id = create_response.json()["data"]["id"]

        version_response = client.post(
            f"/api/v1/agents/{agent_id}/versions",
            json={
                "system_prompt": "Use tools carefully.",
                "model_ref": "model:test:primary",
                "tool_refs": ["tool:test:echo"],
                "verify": True,
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert version_response.status_code == status.HTTP_201_CREATED
        version_id = version_response.json()["data"]["id"]

        publish_response = client.post(
            f"/api/v1/agents/{agent_id}/publish",
            json={"version_id": version_id},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert publish_response.status_code == status.HTTP_200_OK

        execute_response = client.post(
            f"/api/v1/agents/{agent_id}/execute",
            json={
                "messages": [{"role": "user", "content": "Use a tool"}],
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert execute_response.status_code == status.HTTP_200_OK
        payload = execute_response.json()["data"]
        assert payload["output"] == "api tool done"
        assert payload["tool_calls"] == 1

        detail_response = client.get(
            f"/api/v1/responses/{payload['response_id']}/detail",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert detail_response.status_code == status.HTTP_200_OK
        detail_payload = detail_response.json()["data"]
        assert len(detail_payload["tool_calls"]) == 1
        tool_call = detail_payload["tool_calls"][0]
        assert tool_call["tool_name"] == "tool:test:echo"
        assert tool_call["status"] == "completed"
        assert tool_call["arguments_json"] == {"value": "api hi"}
        assert tool_call["result_json"]["result"]["tool_ref"] == "tool:test:echo"

        event_types = [item["type"] for item in detail_payload["events"]]
        assert "tool.call.requested" in event_types
        assert "tool.call.started" in event_types
        assert "tool.call.completed" in event_types
    finally:
        app.dependency_overrides.pop(get_agent_application_service, None)
