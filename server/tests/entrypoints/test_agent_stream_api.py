"""Entry-point tests for the Agent streaming SSE endpoint."""

import asyncio
import json

import pytest
from fastapi import status

from app.api.v1.agent.dependencies import (
    get_agent_application_service,
    get_agent_stream_executor,
)
from app.kernel.ports.llm.interface import ChatResponse, LLMPort, ToolCall
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.runtime.threads.repository import ThreadRepository
from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.agent.application.schemas import AgentRunRequest


class QueueLLMPort(LLMPort):
    def __init__(self, responses):
        self._responses = list(responses)

    async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
        return self._responses.pop(0)

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError


class FailingLLMPort(LLMPort):
    async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
        raise RuntimeError("stream llm unavailable")

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError


class StubToolPort(ToolPort):
    async def invoke(self, tool_ref, parameters, **kwargs):
        return ToolResponse(result={"tool_ref": tool_ref, "parameters": parameters})


def _parse_sse_events(raw: str):
    events = []
    current_event = None
    for line in raw.split("\n"):
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: ") and current_event:
            data = json.loads(line[6:])
            events.append((current_event, data))
            current_event = None
    return events


def test_agent_stream_endpoint_emits_sse_events(client, db, ctx):
    from app.main import app

    async def _override():
        return AgentApplicationService(
            db=db,
            ctx=ctx,
            llm_port=QueueLLMPort([
                ChatResponse(
                    text=None,
                    tokens_prompt=1,
                    tokens_completion=1,
                    finish_reason="tool_calls",
                    tool_calls=[ToolCall(id="call_1", name="tool:test:echo", arguments={"value": "stream hi"})],
                ),
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

    async def _stream_executor(agent_id, inputs, emitter):
        service = await _override()
        return await service.execute_agent_streaming(agent_id, inputs, emitter)

    app.dependency_overrides[get_agent_application_service] = _override
    app.dependency_overrides[get_agent_stream_executor] = lambda: _stream_executor
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
            json={
                "system_prompt": "Stream.",
                "bindings": {"model_ref": "model:test:primary", "tool_refs": ["tool:test:echo"]},
                "verify": True,
            },
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
            json={"input": "Stream now"},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert stream_resp.status_code == status.HTTP_200_OK
        assert "text/event-stream" in stream_resp.headers.get("content-type", "")

        # Parse SSE events from response body
        events = _parse_sse_events(stream_resp.text)

        event_names = [e[0] for e in events]
        assert "agent.run.started" in event_names
        assert "agent.tool.started" in event_names
        assert "agent.tool.succeeded" in event_names
        assert "agent.run.succeeded" in event_names
        assert "agent.result" in event_names

        # Check the result event contains the output
        result_events = [e for e in events if e[0] == "agent.result"]
        assert len(result_events) == 1
        assert result_events[0][1]["output"] == "streamed"
        assert result_events[0][1]["citations"] == []
        assert result_events[0][1]["budget_exceeded"] is False
        thread_id = result_events[0][1]["thread_id"]
        messages = ThreadRepository(db, ctx).list_messages(thread_id)
        assistant_message = next(message for message in messages if message.role == "assistant")
        assert assistant_message.run_id == result_events[0][1]["run_id"]
        assert assistant_message.response_id == result_events[0][1]["response_id"]
        assert assistant_message.model_ref == "model:test:primary"
        assert assistant_message.tokens_prompt == 3
        assert assistant_message.tokens_completion == 3
        assert assistant_message.finish_reason == "tool_calls"
        assert assistant_message.citations_json == []
        assert assistant_message.metadata_json["budget_exceeded"] is False
        assert len(assistant_message.tool_calls_json) == 1
        persisted_tool_call = assistant_message.tool_calls_json[0]
        assert persisted_tool_call["tool_call_id"] == "call_1"
        assert persisted_tool_call["tool_name"] == "tool:test:echo"
        assert persisted_tool_call["tool_type"] == "builtin"
        assert persisted_tool_call["status"] == "completed"
        assert persisted_tool_call["arguments_json"] == {"value": "stream hi"}
        assert persisted_tool_call["result_json"]["result"]["tool_ref"] == "tool:test:echo"
        assert assistant_message.metadata_json["tool_calls"] == assistant_message.tool_calls_json
        assert assistant_message.metadata_json["tool_calls_count"] == 1
        started_tool = next(data for name, data in events if name == "agent.tool.started")
        assert started_tool["tool_ref"] == "tool:test:echo"
        assert started_tool["tool_call_id"] == "call_1"
        completed_tool = next(data for name, data in events if name == "agent.tool.succeeded")
        assert completed_tool["tool_ref"] == "tool:test:echo"
        assert completed_tool["tool_type"] == "builtin"
        assert completed_tool["tool_call_id"] == "call_1"
        assert completed_tool["success"] is True
        assert completed_tool["result"]["result"]["tool_ref"] == "tool:test:echo"
        assert completed_tool["result"]["result"]["parameters"] == {"value": "stream hi"}
    finally:
        app.dependency_overrides.pop(get_agent_application_service, None)
        app.dependency_overrides.pop(get_agent_stream_executor, None)


@pytest.mark.asyncio
async def test_agent_stream_disconnect_does_not_cancel_execution(ctx):
    from app.api.v1.agent.router import stream_agent

    started = asyncio.Event()
    release = asyncio.Event()
    completed = asyncio.Event()
    canceled = False

    class _DetachedService:
        async def execute_agent_streaming(self, agent_id, inputs, emitter):
            nonlocal canceled
            await emitter("agent.run.started", {"run_id": "run_detached"})
            started.set()
            try:
                await release.wait()
                completed.set()
                return {
                    "run_id": "run_detached",
                    "output": "done",
                    "model": "model:test:primary",
                    "iterations": 1,
                }
            except asyncio.CancelledError:
                canceled = True
                raise

    response = await stream_agent(
        "agt_detached",
        AgentRunRequest(input="keep running"),
        ctx,
        _DetachedService().execute_agent_streaming,
    )
    iterator = response.body_iterator
    first_event = await anext(iterator)
    assert "agent.run.started" in first_event
    await iterator.aclose()
    await started.wait()
    release.set()
    await asyncio.wait_for(completed.wait(), timeout=1)

    assert canceled is False


def test_agent_stream_persists_failed_assistant_message_for_chat_history(client, db, ctx):
    from app.main import app

    async def _override():
        return AgentApplicationService(
            db=db,
            ctx=ctx,
            llm_port=FailingLLMPort(),
            tool_port=StubToolPort(),
            memory_service=None,
        )

    async def _stream_executor(agent_id, inputs, emitter):
        service = await _override()
        return await service.execute_agent_streaming(agent_id, inputs, emitter)

    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    app.dependency_overrides[get_agent_application_service] = _override
    app.dependency_overrides[get_agent_stream_executor] = lambda: _stream_executor
    try:
        create_resp = client.post(
            "/api/v1/agents",
            json={"name": "stream-agent-failure", "description": "Stream failure test", "visibility": "private"},
            headers=headers,
        )
        assert create_resp.status_code == status.HTTP_201_CREATED
        agent_id = create_resp.json()["data"]["id"]

        version_resp = client.post(
            f"/api/v1/agents/{agent_id}/versions",
            json={
                "system_prompt": "Stream failure.",
                "bindings": {"model_ref": "model:test:primary"},
                "verify": False,
            },
            headers=headers,
        )
        assert version_resp.status_code == status.HTTP_201_CREATED
        version_id = version_resp.json()["data"]["id"]

        publish_resp = client.post(
            f"/api/v1/agents/{agent_id}/publish",
            json={"version_id": version_id},
            headers=headers,
        )
        assert publish_resp.status_code == status.HTTP_200_OK

        stream_resp = client.post(
            f"/api/v1/agents/{agent_id}/stream",
            json={"input": "Stream and fail"},
            headers=headers,
        )
        assert stream_resp.status_code == status.HTTP_200_OK
        events = _parse_sse_events(stream_resp.text)
        event_names = [name for name, _ in events]
        assert "agent.run.started" in event_names
        assert "agent.run.failed" in event_names
        assert "agent.error" in event_names
        failed_event = next(data for name, data in events if name == "agent.run.failed")
        assert failed_event["run_id"]
        assert failed_event["thread_id"]
        assert failed_event["task_id"]
        assert failed_event["response_id"]
        assert failed_event["error_code"] == "agent_execution_failed"
        assert failed_event["error_message"] == "stream llm unavailable"
        error_event = next(data for name, data in events if name == "agent.error")
        assert error_event["error"] == "stream llm unavailable"

        thread = ThreadRepository(db, ctx).list_threads(agent_id=agent_id)[0]
        assert failed_event["thread_id"] == thread.id
        messages = ThreadRepository(db, ctx).list_messages(thread.id)
        assistant_message = next(message for message in messages if message.role == "assistant")
        assert assistant_message.status == "failed"
        assert assistant_message.content == "Agent execution failed: stream llm unavailable"
        assert assistant_message.error_code == "agent_execution_failed"
        assert assistant_message.error_message == "stream llm unavailable"
        assert assistant_message.finish_reason == "agent_execution_failed"
        assert assistant_message.run_id == thread.latest_run_id == failed_event["run_id"]
        assert assistant_message.response_id == failed_event["response_id"]
        assert assistant_message.metadata_json["error_code"] == "agent_execution_failed"
        assert assistant_message.metadata_json["error_message"] == "stream llm unavailable"
        assert assistant_message.metadata_json["tool_calls_count"] == 0

        thread_response = client.get(f"/api/v1/threads/{thread.id}", headers=headers)
        assert thread_response.status_code == status.HTTP_200_OK
        api_assistant_message = next(
            message for message in thread_response.json()["data"]["messages"] if message["role"] == "assistant"
        )
        assert api_assistant_message["status"] == "failed"
        assert api_assistant_message["content"] == "Agent execution failed: stream llm unavailable"
        assert api_assistant_message["error_code"] == "agent_execution_failed"
        assert api_assistant_message["error_message"] == "stream llm unavailable"
        assert api_assistant_message["finish_reason"] == "agent_execution_failed"
        assert api_assistant_message["run_id"] == thread.latest_run_id
        assert api_assistant_message["response_id"] == assistant_message.response_id
        assert api_assistant_message["metadata_json"]["error_code"] == "agent_execution_failed"
        assert api_assistant_message["metadata_json"]["error_message"] == "stream llm unavailable"
    finally:
        app.dependency_overrides.pop(get_agent_application_service, None)
        app.dependency_overrides.pop(get_agent_stream_executor, None)
