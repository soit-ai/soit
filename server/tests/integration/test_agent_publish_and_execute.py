"""Integration tests for the new Agent aggregate flow."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import ChatResponse, LLMPort, ToolCall
from app.kernel.ports.plugins.interface import PluginRuntimePort
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.tasks.repository import TaskRepository
from app.kernel.runtime.threads.repository import ThreadRepository
from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.agent.application.schemas import (
    AgentCreate,
    AgentRunRequest,
    AgentVersionCreate,
    ChatMessageInput,
)
from app.modules.agent.infra.repository import AgentBindingRepository
from app.modules.evaluation.application.service import RegressionEvaluationService
from app.modules.plugin.domain.models import (
    Plugin,
    PluginInstallation,
    PluginInstalledArtifact,
    PluginVersion,
)


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


class CapturingSkillRuntimePort(PluginRuntimePort):
    """Plugin runtime stub that captures skill context resolution."""

    def __init__(self):
        self.resolved_skill_refs = []

    def list_tools(self, *, plugin_name, version, ctx):
        return []

    async def invoke(self, *, plugin_name, version, tool_name, input_json, ctx, timeout_s=None):
        raise AssertionError("Skill context resolution must not invoke a tool")

    def resolve_skill_context(self, *, skill_refs, ctx):
        self.resolved_skill_refs.append(list(skill_refs))
        return "Bound skill context:\n[skill:triage]\nRuntime rendered triage policy."


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
            "model": request.model_ref,
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
async def test_publish_agent_version_replays_regression_cases_before_publish(db, tenant1_ctx: RequestContext):
    regression_service = RegressionEvaluationService(db=db, ctx=tenant1_ctx)
    service = AgentApplicationService(
        db=db,
        ctx=tenant1_ctx,
        llm_port=QueueLLMPort(
            [
                ChatResponse(
                    text="refund policy evidence",
                    tokens_prompt=3,
                    tokens_completion=4,
                    finish_reason="stop",
                ),
            ]
        ),
        tool_port=StubToolPort(),
        memory_service=StubMemoryService(),
        regression_evaluator=regression_service,
    )
    agent = await service.create_agent(AgentCreate(name="eval-agent"))
    version = await service.create_version(
        agent.id,
        AgentVersionCreate(
            bindings={"model_ref": "model:test:primary"},
            verify=False,
        ),
    )
    run = TraceWriter(db, tenant1_ctx).create_run(
        mode="agent",
        subject_kind="agent",
        subject_id=agent.id,
        subject_version_id="agent_version_old",
        input_summary='{"messages":[{"role":"user","content":"refund policy"}]}',
    )
    regression_service.create_case_from_run(
        run_id=run.id,
        name="refund-policy-regression",
        expected_features={"minimum_output_terms": ["refund policy"], "max_latency_ms": 1000},
    )

    published = await service.publish_version(agent.id, version.id)
    report = regression_service.get_latest_report(
        subject_kind="agent",
        subject_id=agent.id,
        subject_version_id=version.id,
    )

    assert published.published_version_id == version.id
    assert report is not None
    assert report.passed is True
    assert report.summary_json == {"total": 1, "passed": 1, "failed": 0}
    assert report.metrics_json["total_cost_amount"] == 0.0
    assert report.case_results_json[0]["run_id"].startswith("run_")


@pytest.mark.asyncio
async def test_publish_agent_version_blocks_when_regression_report_fails(db, tenant1_ctx: RequestContext):
    regression_service = RegressionEvaluationService(db=db, ctx=tenant1_ctx)
    service = AgentApplicationService(
        db=db,
        ctx=tenant1_ctx,
        llm_port=QueueLLMPort(
            [
                ChatResponse(
                    text="unrelated answer",
                    tokens_prompt=3,
                    tokens_completion=4,
                    finish_reason="stop",
                ),
            ]
        ),
        tool_port=StubToolPort(),
        memory_service=StubMemoryService(),
        regression_evaluator=regression_service,
    )
    agent = await service.create_agent(AgentCreate(name="eval-failure-agent"))
    version = await service.create_version(
        agent.id,
        AgentVersionCreate(
            bindings={"model_ref": "model:test:primary"},
            verify=False,
        ),
    )
    run = TraceWriter(db, tenant1_ctx).create_run(
        mode="agent",
        subject_kind="agent",
        subject_id=agent.id,
        subject_version_id="agent_version_old",
        input_summary='{"messages":[{"role":"user","content":"refund policy"}]}',
    )
    regression_service.create_case_from_run(
        run_id=run.id,
        name="refund-policy-regression",
        expected_features={"minimum_output_terms": ["refund policy"]},
    )

    with pytest.raises(ValidationError) as exc:
        await service.publish_version(agent.id, version.id)
    report = regression_service.get_latest_report(
        subject_kind="agent",
        subject_id=agent.id,
        subject_version_id=version.id,
    )
    current = await service.get_agent(agent.id)

    assert exc.value.details["status"] == "regression_failed"
    assert current.published_version_id is None
    assert report is not None
    assert report.passed is False
    assert report.summary_json == {"total": 1, "passed": 0, "failed": 1}


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
    assert not any(binding.binding_type == "plugin" for binding in bindings)
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
    assert messages[2].model_ref == result["model"]
    assert messages[2].tokens_prompt == result["tokens_prompt"]
    assert messages[2].tokens_completion == result["tokens_completion"]
    assert messages[2].finish_reason == result["finish_reason"]
    assert (messages[2].metadata_json or {})["budget_exceeded"] is False
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
    assert response.usage_json["budget_exceeded"] is False
    assert response.usage_json["budget_reason"] is None
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
async def test_execute_agent_persists_knowledge_citations_in_response_output(
    db,
    tenant1_ctx: RequestContext,
    monkeypatch,
):
    async def fake_knowledge_query(**_kwargs):
        return {
            "results": [
                {
                    "chunk_id": "chunk_1",
                    "document_id": "doc_1",
                    "score": 0.91,
                    "text": "Refund tickets require account verification before escalation.",
                    "metadata": {},
                }
            ],
            "total": 1,
            "citations": [
                {
                    "chunk_id": "chunk_1",
                    "document_id": "doc_1",
                    "rank": 1,
                    "score": 0.91,
                    "doc_key": "refund-policy.md",
                    "title": "Refund Policy",
                    "chunk_no": 3,
                    "snippet": "Refund tickets require account verification before escalation.",
                }
            ],
        }

    monkeypatch.setattr("app.modules.knowledge.application.tools.knowledge_query", fake_knowledge_query)

    service = AgentApplicationService(
        db=db,
        ctx=tenant1_ctx,
        llm_port=QueueLLMPort(
            [
                ChatResponse(
                    text="Verify the account before escalating the refund ticket.",
                    tokens_prompt=4,
                    tokens_completion=6,
                    finish_reason="stop",
                ),
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
            name="ops-agent-citations",
            description="Execution citation test agent",
            visibility="private",
            tags=["ops"],
        )
    )
    version = await service.create_version(
        agent.id,
        AgentVersionCreate(
            system_prompt="Use cited enterprise knowledge.",
            temperature=0.1,
            bindings={
                "model_ref": "model:test:primary",
                "knowledge_refs": ["knowledge:kb_demo"],
            },
            verify=False,
        ),
    )
    await service.publish_version(agent.id, version.id)

    result = await service.execute_agent(
        agent.id,
        AgentRunRequest(
            messages=[ChatMessageInput(role="user", content="How should we handle refund tickets?")],
        ).model_dump(exclude_none=True),
    )

    response, _, _ = service.response_service.get_response_detail(result["response_id"])

    assert result["citations"] == [
        {
            "chunk_id": "chunk_1",
            "document_id": "doc_1",
            "rank": 1,
            "score": 0.91,
            "doc_key": "refund-policy.md",
            "title": "Refund Policy",
            "chunk_no": 3,
            "snippet": "Refund tickets require account verification before escalation.",
            "knowledge_id": "kb_demo",
        }
    ]
    assert response.output_json["citations"] == result["citations"]
    messages = ThreadRepository(db, tenant1_ctx).list_messages(result["thread_id"])
    assistant_message = next(message for message in messages if message.role == "assistant")
    assert assistant_message.citations_json == result["citations"]
    assert assistant_message.tokens_prompt == 5
    assert assistant_message.tokens_completion == 7
    assert assistant_message.metadata_json["citations"] == result["citations"]


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

    with pytest.raises(PydanticValidationError, match="Extra inputs are not permitted"):
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
async def test_execute_agent_resolves_runtime_request_from_published_version(db, tenant1_ctx: RequestContext, monkeypatch):
    skill_runtime = CapturingSkillRuntimePort()
    service = AgentApplicationService(
        db=db,
        ctx=tenant1_ctx,
        llm_port=QueueLLMPort([]),
        tool_port=StubToolPort(),
        memory_service=StubMemoryService(),
        plugin_runtime_port=skill_runtime,
    )
    runner = CapturingRunner()
    monkeypatch.setattr(service, "_build_runner", lambda: runner)
    plugin_spec = {
        "name": "workspace-skill-triage",
        "publisher": "workspace",
        "version": "1.0.0",
        "plugin_type": "skill",
        "exports": {"skills": ["skill:triage"]},
    }
    plugin = Plugin(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        name="workspace-skill-triage",
        version="1.0.0",
        publisher="workspace",
        plugin_type="skill",
        status="active",
        spec_json=plugin_spec,
        manifest_json={"spec": plugin_spec},
        publish_status="published",
        installed_count=1,
    )
    db.add(plugin)
    db.commit()
    db.refresh(plugin)
    plugin_version = PluginVersion(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        plugin_id=plugin.id,
        version=1,
        package_version="1.0.0",
        status="published",
        spec_json=plugin_spec,
        manifest_json={"spec": plugin_spec},
        artifact_summary_json={"skills": ["skill:triage"]},
    )
    db.add(plugin_version)
    db.commit()
    db.refresh(plugin_version)
    plugin.current_version_id = plugin_version.id
    plugin.published_version_id = plugin_version.id
    installation = PluginInstallation(
        tenant_id=tenant1_ctx.tenant_id,
        workspace_id=tenant1_ctx.workspace_id,
        plugin_id=plugin.id,
        plugin_version_id=plugin_version.id,
        enabled=True,
        state="installed",
        config_json={"enabled": True},
    )
    db.add(installation)
    db.commit()
    db.refresh(installation)
    db.add(
        PluginInstalledArtifact(
            tenant_id=tenant1_ctx.tenant_id,
            workspace_id=tenant1_ctx.workspace_id,
            plugin_id=plugin.id,
            plugin_version_id=plugin_version.id,
            installation_id=installation.id,
            artifact_kind="skill",
            artifact_ref="skill:triage",
            artifact_id="skill:triage",
            artifact_version_id=None,
            enabled=True,
            state="enabled",
            metadata_json={
                "skill": {
                    "name": "triage",
                    "description": "Ticket triage skill",
                    "category": "agent",
                    "spec_json": {"instructions": "Escalate urgent customer tickets."},
                }
            },
        )
    )
    db.commit()

    agent = await service.create_agent(
        AgentCreate(
            name="ops-agent-runtime-contract",
            description="Runtime contract test agent",
            visibility="private",
            tags=["ops"],
        )
    )
    version = await service.create_version(
        agent.id,
        AgentVersionCreate(
            system_prompt="Use the published contract.",
            temperature=0.2,
            bindings={
                "model_ref": "model:test:published",
                "knowledge_refs": ["knowledge:test:support"],
                "tool_refs": ["tool:test:echo"],
                "workflow_refs": ["wf:handoff"],
                "skill_refs": ["skill:triage"],
            },
            verify=False,
        ),
    )
    await service.publish_version(agent.id, version.id)

    result = await service.execute_agent(
        agent.id,
        AgentRunRequest(
            messages=[ChatMessageInput(role="user", content="Run the task")],
        ).model_dump(exclude_none=True),
    )

    assert result["output"] == "captured"
    assert runner.request is not None
    assert runner.request.model_ref == "model:test:published"
    assert runner.request.temperature == 0.2
    assert runner.request.knowledge_refs == ["knowledge:test:support"]
    assert runner.request.tool_refs == ["tool:test:echo"]
    assert runner.request.workflow_refs == ["wf:handoff"]
    assert runner.request.skill_refs == ["skill:triage"]
    assert runner.request.memory_strategy is None
    assert runner.request.memory_top_k is None
    assert runner.request.system_prompt == "Use the published contract."
    assert runner.request.messages[0].role == "system"
    assert "Use the published contract." in runner.request.messages[0].content
    assert "Bound skill context:" in runner.request.messages[0].content
    assert "Runtime rendered triage policy." in runner.request.messages[0].content
    assert skill_runtime.resolved_skill_refs == [["skill:triage"]]


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
