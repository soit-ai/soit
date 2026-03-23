"""Integration tests for the new Agent aggregate flow."""

from types import SimpleNamespace

import pytest

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import ChatResponse, LLMPort
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.responses.repository import ResponseEventRepository, ResponseRepository
from app.kernel.runtime.repository import TaskRepository, ThreadRepository
from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.agent.application.schemas import AgentCreate, AgentRunRequest, AgentVersionCreate
from app.modules.agent.infra.repository import AgentBindingRepository
from app.modules.agent.application.schemas import ChatMessageInput


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


class StubMemoryService:
    """Memory stub returning one summary."""

    async def query_memory(self, data, run_id=None):
        memory = SimpleNamespace(content_summary="remembered", content={"text": "remembered"})
        return [SimpleNamespace(memory=memory, score=0.9)]


@pytest.mark.asyncio
async def test_publish_and_execute_agent_creates_bindings_threads_and_tasks(db, tenant1_ctx: RequestContext):
    service = AgentApplicationService(
        db=db,
        ctx=tenant1_ctx,
        llm_port=QueueLLMPort(
            [
                ChatResponse(
                    text='{"action":"respond","response":"agent done"}',
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
        memory_service=StubMemoryService(),
    )

    agent = await service.create_agent(
        AgentCreate(
            name="ops-agent",
            description="Execution test agent",
            visibility="private",
            tags=["ops"],
        )
    )
    version = await service.create_version(
        agent.id,
        AgentVersionCreate(
            system_prompt="You are precise.",
            model_ref="model:test:primary",
            temperature=0.1,
            tool_refs=["tool:test:echo"],
            memory_strategy="planner_only",
            memory_top_k=3,
            verify=True,
        ),
    )
    published = await service.publish_version(agent.id, version.id)
    result = await service.execute_agent(
        agent.id,
        AgentRunRequest(
            messages=[ChatMessageInput(role="user", content="Run the task")],
        ).model_dump(exclude_none=True),
    )

    binding_repo = AgentBindingRepository(db, tenant1_ctx)
    bindings = binding_repo.list_for_version(version.id)
    thread_repo = ThreadRepository(db, tenant1_ctx)
    task_repo = TaskRepository(db, tenant1_ctx)
    response_repo = ResponseRepository(db, tenant1_ctx)
    response_event_repo = ResponseEventRepository(db, tenant1_ctx)
    messages = thread_repo.list_messages(result["thread_id"])
    task = task_repo.get_task(result["task_id"])
    events = task_repo.list_events(result["task_id"])
    response = response_repo.get(result["response_id"])
    response_events = response_event_repo.list_for_response(result["response_id"], limit=20, offset=0)

    assert published.published_version_id == version.id
    assert any(binding.binding_type == "model" and binding.target_key == "model:test:primary" for binding in bindings)
    assert any(binding.binding_type == "tool" and binding.target_key == "tool:test:echo" for binding in bindings)
    assert result["output"] == "agent done"
    assert result["response_id"].startswith("resp_")
    assert result["thread_id"].startswith("thr_")
    assert result["task_id"].startswith("task_")
    assert len(messages) == 3
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert messages[2].role == "assistant"
    assert (messages[2].metadata_json or {})["response_id"] == result["response_id"]
    assert task is not None
    assert task.status == "succeeded"
    assert task.output_json["output"] == "agent done"
    assert response is not None
    assert response.run_id == result["run_id"]
    assert response.status == "completed"
    assert [event.type for event in response_events] == [
        "response.created",
        "response.input.added",
        "response.output_text.completed",
        "response.completed",
    ]
    assert [event.event_type for event in events] == ["task.created", "task.status", "task.status"]


@pytest.mark.asyncio
async def test_execute_agent_records_tool_calls_in_response_detail(db, tenant1_ctx: RequestContext):
    service = AgentApplicationService(
        db=db,
        ctx=tenant1_ctx,
        llm_port=QueueLLMPort(
            [
                ChatResponse(
                    text='{"action":"tool","tool_ref":"tool:test:echo","parameters":{"value":"hi"}}',
                    tokens_prompt=1,
                    tokens_completion=1,
                    finish_reason="stop",
                ),
                ChatResponse(
                    text='{"action":"respond","response":"agent tool done"}',
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
        memory_service=StubMemoryService(),
    )

    agent = await service.create_agent(
        AgentCreate(
            name="ops-agent-tools",
            description="Execution tool-call test agent",
            visibility="private",
            tags=["ops"],
        )
    )
    version = await service.create_version(
        agent.id,
        AgentVersionCreate(
            system_prompt="You are precise.",
            model_ref="model:test:primary",
            temperature=0.1,
            tool_refs=["tool:test:echo"],
            memory_strategy="planner_only",
            memory_top_k=3,
            verify=True,
        ),
    )
    await service.publish_version(agent.id, version.id)
    result = await service.execute_agent(
        agent.id,
        AgentRunRequest(
            messages=[ChatMessageInput(role="user", content="Run the tool task")],
        ).model_dump(exclude_none=True),
    )

    response_repo = ResponseRepository(db, tenant1_ctx)
    response_event_repo = ResponseEventRepository(db, tenant1_ctx)
    response = response_repo.get(result["response_id"])
    response_events = response_event_repo.list_for_response(result["response_id"], limit=20, offset=0)
    _, _, tool_calls = service.response_service.get_response_detail(result["response_id"])

    assert result["output"] == "agent tool done"
    assert result["tool_calls"] == 1
    assert response is not None
    assert response.status == "completed"
    assert len(tool_calls) == 1
    assert tool_calls[0]["tool_name"] == "tool:test:echo"
    assert tool_calls[0]["status"] == "completed"
    assert tool_calls[0]["arguments_json"] == {"value": "hi"}
    assert tool_calls[0]["result_json"]["result"]["tool_ref"] == "tool:test:echo"
    assert [event.type for event in response_events] == [
        "response.created",
        "response.input.added",
        "tool.call.requested",
        "tool.call.started",
        "tool.call.completed",
        "response.output_text.completed",
        "response.completed",
    ]
