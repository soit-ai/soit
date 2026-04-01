"""Entry-point tests for the Agent streaming SSE endpoint."""

import json

from fastapi import status

from app.api.v1.agent.dependencies import get_agent_application_service
from app.kernel.ports.llm.interface import ChatResponse, LLMPort, ToolCall
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.modules.agent.application.application_service import AgentApplicationService


class QueueLLMPort(LLMPort):
    def __init__(self, responses):
        self._responses = list(responses)

    async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
        return self._responses.pop(0)

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError


class StubToolPort(ToolPort):
    async def invoke(self, tool_ref, parameters, **kwargs):
        return ToolResponse(result={"tool_ref": tool_ref, "parameters": parameters})


def test_agent_stream_endpoint_emits_sse_events(client, db, ctx):
    from app.main import app

    async def _override():
        return AgentApplicationService(
            db=db,
            ctx=ctx,
            llm_port=QueueLLMPort([
                ChatResponse(text="streamed", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
                ChatResponse(
                    text=None,
                    tokens_prompt=1,
                    tokens_completion=1,
                    finish_reason="tool_calls",
                    tool_calls=[ToolCall(id="call_v", name="verify_response", arguments={"ok": True, "reason": "ok"})],
                ),
            ]),
            tool_port=StubToolPort(),
            memory_service=None,
        )

    app.dependency_overrides[get_agent_application_service] = _override
    try:
        # Create and publish agent
        create_resp = client.post(
            "/api/v1/agents",
            json={"name": "stream-agent", "description": "Stream test", "visibility": "private"},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert create_resp.status_code == status.HTTP_201_CREATED
        agent_id = create_resp.json()["data"]["id"]

        version_resp = client.post(
            f"/api/v1/agents/{agent_id}/versions",
            json={"system_prompt": "Stream.", "model_ref": "model:test:primary", "verify": True},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert version_resp.status_code == status.HTTP_201_CREATED
        version_id = version_resp.json()["data"]["id"]

        publish_resp = client.post(
            f"/api/v1/agents/{agent_id}/publish",
            json={"version_id": version_id},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert publish_resp.status_code == status.HTTP_200_OK

        # Call stream endpoint
        stream_resp = client.post(
            f"/api/v1/agents/{agent_id}/stream",
            json={"messages": [{"role": "user", "content": "Stream now"}]},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert stream_resp.status_code == status.HTTP_200_OK
        assert "text/event-stream" in stream_resp.headers.get("content-type", "")

        # Parse SSE events from response body
        raw = stream_resp.text
        events = []
        current_event = None
        for line in raw.split("\n"):
            if line.startswith("event: "):
                current_event = line[7:]
            elif line.startswith("data: ") and current_event:
                data = json.loads(line[6:])
                events.append((current_event, data))
                current_event = None

        event_names = [e[0] for e in events]
        assert "agent.run.started" in event_names
        assert "agent.run.completed" in event_names
        assert "agent.result" in event_names

        # Check the result event contains the output
        result_events = [e for e in events if e[0] == "agent.result"]
        assert len(result_events) == 1
        assert result_events[0][1]["output"] == "streamed"
    finally:
        app.dependency_overrides.pop(get_agent_application_service, None)
