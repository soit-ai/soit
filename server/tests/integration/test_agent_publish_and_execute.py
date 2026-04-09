"""Integration tests for the new Agent aggregate flow."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import ChatResponse, LLMPort, ToolCall
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.responses.repository import ResponseEventRepository, ResponseRepository
from app.kernel.runtime.repository import TaskRepository, ThreadRepository
from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.agent.application.schemas import AgentCreate, AgentRunRequest, AgentVersionCreate
from app.modules.agent.infra.repository import AgentBindingRepository
from app.modules.agent.application.schemas import ChatMessageInput


class QueueLLMPort(LLMPort):
    """LLM stub returning queued responses."""

    def __init__(self, responses):
        self._responses = list(responses)

    async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
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


class CapturingRunner:
    """Runner stub that captures the request passed by execute_agent."""

    def __init__(self):
        self.request = None

    async def run(self, request, existing_run_id=None, response_id=None, event_emitter=None):
        self.request = request
        return {
            "run_id": existing_run_id or "run_capture",
            "output": "captured",
            "model": request.model,
            "iterations": 1,
            "tokens_prompt": 0,
            "tokens_completion": 0,
            "finish_reason": "stop",
            "tool_calls": 0,
            "llm_calls": 1,
            "failures": 0,
            "budget_exceeded": False,
            "budget_reason": None,
            "cost_total": 0.0,
        }


@pytest.mark.asyncio
async def test_publish_and_execute_agent_creates_bindings_threads_and_tasks(db, tenant1_ctx: RequestContext):
    service = AgentApplicationService(
        db=db,
        ctx=tenant1_ctx,
        llm_port=QueueLLMPort(
            [
                # Plan: respond
                ChatResponse(
                    text="agent done",
                    tokens_prompt=1,
                    tokens_completion=1,
                    finish_reason="stop",
                ),
                # Verify: ok
                ChatResponse(
                    text=None,
                    tokens_prompt=1,
                    tokens_completion=1,
                    finish_reason="tool_calls",
                    tool_calls=[ToolCall(id="call_v", name="verify_response", arguments={"ok": True, "reason": "ok"})],
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
            temperature=0.1,
            bindings={
                "model_ref": "model:test:primary",
                "knowledge_refs": [
                    "knowledge:test:support",
                    "knowledge:test:support",
                    "knowledge:test:faq",
                    "knowledge:test:support",
                ],
                "tool_refs": [
                    "tool:test:echo",
                    "tool:test:echo",
                    "tool:test:search",
                    "tool:test:echo",
                ],
                "workflow_refs": ["wf:handoff"],
                "skill_refs": ["skill:triage"],
                "plugin_refs": ["plugin:soit:search:1.0.0"],
            },
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
    assert published.default_model_ref == "model:test:primary"
    assert version.spec_json["bindings"]["model_ref"] == "model:test:primary"
    assert version.spec_json["bindings"]["knowledge_refs"] == [
        "knowledge:test:support",
        "knowledge:test:faq",
    ]
    assert version.spec_json["bindings"]["tool_refs"] == [
        "tool:test:echo",
        "tool:test:search",
    ]
    assert version.spec_json["temperature"] == 0.1
    assert "model" not in version.spec_json
    assert "tools" not in version.spec_json
    assert "rag" not in version.spec_json
    assert any(binding.binding_type == "model" and binding.target_key == "model:test:primary" for binding in bindings)
    knowledge_bindings = [binding.target_key for binding in bindings if binding.binding_type == "knowledge"]
    tool_bindings = [binding.target_key for binding in bindings if binding.binding_type == "tool"]
    assert knowledge_bindings == ["knowledge:test:support", "knowledge:test:faq"]
    assert tool_bindings == ["tool:test:echo", "tool:test:search"]
    assert any(binding.binding_type == "workflow" and binding.target_key == "wf:handoff" for binding in bindings)
    assert any(binding.binding_type == "skill" and binding.target_key == "skill:triage" for binding in bindings)
    assert any(binding.binding_type == "plugin" and binding.target_key == "plugin:soit:search:1.0.0" for binding in bindings)
    assert result["output"] == "agent done"
    assert result["model"] == "model:test:primary"
    assert result["response_id"].startswith("resp_")
    assert result["thread_id"].startswith("thr_")
    assert result["task_id"].startswith("task_")
    assert len(messages) == 3
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert messages[2].role == "assistant"
    assert (messages[2].metadata_json or {})["response_id"] == result["response_id"]
    assert messages[2].model_ref is None
    assert messages[2].tokens_prompt is None
    assert messages[2].tokens_completion is None
    assert messages[2].finish_reason is None
    assert task is not None
    assert task.run_id == result["run_id"]
    assert task.status == "succeeded"
    assert task.output_json["output"] == "agent done"
    assert task.output_json["response_id"] == result["response_id"]
    assert "run_id" not in task.output_json
    assert "thread_id" not in task.output_json
    assert "tokens_prompt" not in task.output_json
    assert "tokens_completion" not in task.output_json
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
                # Plan: call tool
                ChatResponse(
                    text=None,
                    tokens_prompt=1,
                    tokens_completion=1,
                    finish_reason="tool_calls",
                    tool_calls=[ToolCall(id="call_1", name="tool:test:echo", arguments={"value": "hi"})],
                ),
                # Plan: respond
                ChatResponse(
                    text="agent tool done",
                    tokens_prompt=1,
                    tokens_completion=1,
                    finish_reason="stop",
                ),
                # Verify: ok
                ChatResponse(
                    text=None,
                    tokens_prompt=1,
                    tokens_completion=1,
                    finish_reason="tool_calls",
                    tool_calls=[ToolCall(id="call_v", name="verify_response", arguments={"ok": True, "reason": "ok"})],
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
            temperature=0.1,
            bindings={
                "model_ref": "model:test:primary",
                "tool_refs": ["tool:test:echo"],
            },
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
    assert [event.type for event in response_events] == [
        "response.created",
        "response.input.added",
        "tool.call.requested",
        "tool.call.started",
        "tool.call.completed",
        "response.output_text.completed",
        "response.completed",
    ]


@pytest.mark.asyncio
async def test_execute_agent_rejects_execution_override_keys_from_direct_service_call(db, tenant1_ctx: RequestContext):
    service = AgentApplicationService(
        db=db,
        ctx=tenant1_ctx,
        llm_port=QueueLLMPort([]),
        tool_port=StubToolPort(),
        memory_service=StubMemoryService(),
    )

    agent = await service.create_agent(
        AgentCreate(
            name="ops-agent-spec-wins",
            description="Execution override contract test agent",
            visibility="private",
            tags=["ops"],
        )
    )
    version = await service.create_version(
        agent.id,
        AgentVersionCreate(
            system_prompt="You are precise.",
            temperature=0.1,
            bindings={
                "model_ref": "model:test:primary",
                "knowledge_refs": ["knowledge:test:support"],
                "tool_refs": ["tool:test:echo"],
            },
            verify=True,
        ),
    )
    await service.publish_version(agent.id, version.id)

    with pytest.raises(PydanticValidationError, match="Execution overrides are not supported for"):
        await service.execute_agent(
            agent.id,
            {
                "messages": [{"role": "user", "content": "Run the task"}],
                "model": "model:test:override",
                "temperature": 0.9,
                "tool_refs": ["tool:test:override"],
                "knowledge_refs": ["knowledge:test:override"],
            },
        )


@pytest.mark.asyncio
async def test_execute_agent_requires_published_version(db, tenant1_ctx: RequestContext):
    service = AgentApplicationService(
        db=db,
        ctx=tenant1_ctx,
        llm_port=QueueLLMPort([]),
        tool_port=StubToolPort(),
        memory_service=StubMemoryService(),
    )

    agent = await service.create_agent(
        AgentCreate(
            name="ops-agent-draft-only",
            description="Draft-only execution test agent",
            visibility="private",
            tags=["ops"],
        )
    )
    await service.create_version(
        agent.id,
        AgentVersionCreate(
            system_prompt="You are precise.",
            bindings={"model_ref": "model:test:primary"},
            verify=True,
        ),
    )

    with pytest.raises(ValidationError, match="published version"):
        await service.execute_agent(
            agent.id,
            AgentRunRequest(
                messages=[ChatMessageInput(role="user", content="Run the task")],
            ).model_dump(exclude_none=True),
        )
