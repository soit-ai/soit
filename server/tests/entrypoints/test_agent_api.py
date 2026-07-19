"""Entry-point tests for the Agent API."""

from fastapi import status
from sqlalchemy import select

from app.api.v1.agent.dependencies import get_agent_application_service
from app.kernel.ports.llm.interface import ChatResponse, LLMPort, ToolCall
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.ports.tools.policy import ToolPolicyGateway
from app.kernel.runtime.db.models.runs import Run, RunStepToolCall
from app.kernel.runtime.db.models.tasks import Task
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter
from app.kernel.runtime.tasks.service import TaskService
from app.kernel.runtime.threads.repository import ThreadRepository
from app.modules.agent.application.application_service import AgentApplicationService


class QueueLLMPort(LLMPort):
    """LLM stub returning queued JSON payloads."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.messages = []

    async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
        self.messages.append(messages)
        return self._responses.pop(0)

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError


class StubToolPort(ToolPort):
    """Tool stub with deterministic success."""

    async def invoke(self, tool_ref, parameters, **kwargs):
        return ToolResponse(result={"tool_ref": tool_ref, "parameters": parameters})


class FailingLLMPort(LLMPort):
    """LLM stub that fails during planning."""

    async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
        raise RuntimeError("llm unavailable")

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError


def test_agent_api_create_publish_and_execute(client, db, ctx):
    from app.main import app

    llm_port = QueueLLMPort(
        [
            ChatResponse(text="api done", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
            ChatResponse(
                text=None,
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="tool_calls",
                tool_calls=[
                    ToolCall(
                        id="call_v1",
                        name="verify_response",
                        arguments={"ok": True, "reason": "ok"},
                    )
                ],
            ),
            ChatResponse(text="continued", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
            ChatResponse(
                text=None,
                tokens_prompt=1,
                tokens_completion=1,
                finish_reason="tool_calls",
                tool_calls=[
                    ToolCall(
                        id="call_v2",
                        name="verify_response",
                        arguments={"ok": True, "reason": "ok"},
                    )
                ],
            ),
        ]
    )

    async def _override_agent_application_service() -> AgentApplicationService:
        return AgentApplicationService(
            db=db,
            ctx=ctx,
            llm_port=llm_port,
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
                "bindings": {
                    "model_ref": "model:test:primary",
                    "knowledge_refs": ["knowledge:kb_support"],
                    "tool_refs": ["tool:test:echo"],
                    "workflow_refs": ["wf:handoff"],
                    "skill_refs": ["skill:triage"],
                },
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
        assert "workflow" in binding_types
        assert "skill" in binding_types
        assert "plugin" not in binding_types

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
                "input": "Execute now",
                "request_id": "req_execute_now",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert execute_response.status_code == status.HTTP_200_OK
        payload = execute_response.json()["data"]
        assert payload["output"] == "api done"
        assert payload["response_id"].startswith("resp_")
        assert payload["thread_id"].startswith("thr_")
        assert payload["task_id"].startswith("task_")
        task = db.get(Task, payload["task_id"])
        assert task is not None
        assert task.run_id == payload["run_id"]
        run = db.get(Run, payload["run_id"])
        assert run is not None
        assert run.request_id == "req_execute_now"
        assert "run_id" not in (task.output_json or {})
        assert "thread_id" not in (task.output_json or {})

        linked_response = client.get(
            f"/api/v1/responses/{payload['response_id']}",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert linked_response.status_code == status.HTTP_200_OK
        assert linked_response.json()["data"]["run_id"] == payload["run_id"]
        assert linked_response.json()["data"]["request_id"] == "req_execute_now"

        continued_response = client.post(
            f"/api/v1/agents/{agent_id}/execute",
            json={
                "input": "Continue from the prior result",
                "thread_id": payload["thread_id"],
                "request_id": "req_execute_continue",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert continued_response.status_code == status.HTTP_200_OK
        continued = continued_response.json()["data"]
        assert continued["output"] == "continued"
        assert continued["thread_id"] == payload["thread_id"]
        second_turn_messages = llm_port.messages[2]
        assert [message.role for message in second_turn_messages] == [
            "system",
            "user",
            "assistant",
            "user",
        ]
        assert [message.content for message in second_turn_messages[1:]] == [
            "Execute now",
            "api done",
            "Continue from the prior result",
        ]

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
                    # Plan: call tool
                    ChatResponse(
                        text=None,
                        tokens_prompt=1,
                        tokens_completion=1,
                        finish_reason="tool_calls",
                        tool_calls=[ToolCall(id="call_1", name="tool:test:echo", arguments={"value": "api hi"})],
                    ),
                    # Plan: respond
                    ChatResponse(
                        text="api tool done",
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
                "bindings": {
                    "model_ref": "model:test:primary",
                    "tool_refs": ["tool:test:echo"],
                },
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
                "input": "Use a tool",
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


def test_agent_api_explicit_cancel_closes_run_task_and_response(client, db, ctx):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    create_response = client.post(
        "/api/v1/agents",
        json={"name": "cancelable-agent", "visibility": "private"},
        headers=headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    agent_id = create_response.json()["data"]["id"]

    trace_writer = TraceWriter(db, ctx)
    run = trace_writer.create_run(
        mode="agent",
        kind="agent",
        subject_kind="agent",
        subject_id=agent_id,
        subject_version_id="agtv_cancel",
        request_id="req_cancel_agent",
    )
    trace_writer.update_run_status(run.id, "running")
    task_service = TaskService(db, ctx)
    task = task_service.create_task(
        task_type="agent.stream",
        agent_id=agent_id,
        run_id=run.id,
    )
    task_service.transition_task(task_id=task.id, status="running")
    response_service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=trace_writer,
    )
    response = response_service.create_linked_response(
        run_id=run.id,
        task_id=task.id,
        agent_id=agent_id,
        request_id="req_cancel_agent",
    )
    response_service.mark_running(response)

    cancel_response = client.post(
        f"/api/v1/agents/{agent_id}/runs/{run.id}/cancel",
        headers=headers,
    )

    assert cancel_response.status_code == status.HTTP_200_OK
    payload = cancel_response.json()["data"]
    assert payload["status"] == "canceled"
    assert payload["task_ids"] == [task.id]
    assert payload["response_ids"] == [response.id]
    db.expire_all()
    assert db.get(Run, run.id).status == "canceled"
    assert db.get(Task, task.id).status == "canceled"
    assert ResponseRepository(db, ctx).get(response.id).status == "canceled"


def test_agent_api_workbench_returns_agent_rows_and_runtime_metrics(client, db, ctx):
    from app.kernel.commons.time import utc_now
    from app.kernel.runtime.db.models.runs import Run
    from app.main import app

    async def _override_agent_application_service() -> AgentApplicationService:
        return AgentApplicationService(
            db=db,
            ctx=ctx,
            llm_port=QueueLLMPort([]),
            tool_port=StubToolPort(),
            memory_service=None,
        )

    app.dependency_overrides[get_agent_application_service] = _override_agent_application_service
    try:
        headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
        published_response = client.post(
            "/api/v1/agents",
            json={"name": "Published Agent", "description": "Ready for runtime", "visibility": "private"},
            headers=headers,
        )
        assert published_response.status_code == status.HTTP_201_CREATED
        published_agent_id = published_response.json()["data"]["id"]

        draft_response = client.post(
            "/api/v1/agents",
            json={"name": "Draft Agent", "description": "Needs configuration", "visibility": "private"},
            headers=headers,
        )
        assert draft_response.status_code == status.HTTP_201_CREATED

        version_response = client.post(
            f"/api/v1/agents/{published_agent_id}/versions",
            json={
                "system_prompt": "Use configured capabilities.",
                "bindings": {
                    "model_ref": "model:test:primary",
                    "knowledge_refs": ["knowledge:support"],
                    "tool_refs": ["tool:test:echo"],
                },
                "verify": False,
            },
            headers=headers,
        )
        assert version_response.status_code == status.HTTP_201_CREATED
        version_id = version_response.json()["data"]["id"]

        publish_response = client.post(
            f"/api/v1/agents/{published_agent_id}/publish",
            json={"version_id": version_id},
            headers=headers,
        )
        assert publish_response.status_code == status.HTTP_200_OK

        now = utc_now()
        db.add_all(
            [
                Run(
                    id="run_workbench_success",
                    tenant_id=ctx.tenant_id,
                    workspace_id=ctx.workspace_id,
                    mode="agent",
                    kind="agent",
                    subject_kind="agent",
                    subject_id=published_agent_id,
                    subject_version_id=version_id,
                    status="succeeded",
                    input_summary="hello",
                    output_summary="done",
                    started_at=now,
                    ended_at=now,
                    duration_ms=120,
                ),
                Run(
                    id="run_workbench_failed",
                    tenant_id=ctx.tenant_id,
                    workspace_id=ctx.workspace_id,
                    mode="agent",
                    kind="agent",
                    subject_kind="agent",
                    subject_id=published_agent_id,
                    subject_version_id=version_id,
                    status="failed",
                    input_summary="fail",
                    error_message="tool failed",
                    started_at=now,
                    ended_at=now,
                    duration_ms=280,
                ),
            ]
        )
        db.commit()

        response = client.get("/api/v1/agents/workbench?page_size=20", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()["data"]
        assert payload["summary"]["total_agents"] == 2
        assert payload["summary"]["configured_agents"] == 1
        assert payload["summary"]["running_agents"] == 1
        assert payload["summary"]["today_calls"] == 2
        assert payload["summary"]["avg_latency_ms"] == 200
        assert payload["summary"]["success_rate"] == 50.0
        assert payload["summary"]["pending_exceptions"] == 1
        assert payload["tabs"]["all"] == 2
        assert payload["tabs"]["unconfigured"] == 1
        assert payload["tabs"]["low_success"] == 1
        assert payload["tabs"]["long_latency"] == 0

        published_row = next(item for item in payload["items"] if item["id"] == published_agent_id)
        assert published_row["status"] == "abnormal"
        assert published_row["today_calls"] == 2
        assert published_row["avg_latency_ms"] == 200
        assert published_row["success_rate"] == 50.0
        assert published_row["recent_exception_count"] == 1
        assert published_row["action_enabled"] is True
        assert [capability["type"] for capability in published_row["capabilities"]] == ["model", "knowledge", "tool"]

        draft_row = next(item for item in payload["items"] if item["name"] == "Draft Agent")
        assert draft_row["status"] == "unconfigured"
        assert draft_row["action_enabled"] is False

        items_response = client.get(
            "/api/v1/agents/workbench/items?tab=low-success&keyword=Published&page_size=1",
            headers=headers,
        )
        assert items_response.status_code == status.HTTP_200_OK
        items_payload = items_response.json()["data"]
        assert "summary" not in items_payload
        assert items_payload["page_size"] == 1
        assert items_payload["next_page_token"] is None
        assert [item["id"] for item in items_payload["items"]] == [published_agent_id]

        paged_response = client.get("/api/v1/agents/workbench/items?page_size=1", headers=headers)
        assert paged_response.status_code == status.HTTP_200_OK
        assert paged_response.json()["data"]["next_page_token"] is not None
    finally:
        app.dependency_overrides.pop(get_agent_application_service, None)


def test_agent_api_workflow_binding_executes_ticket_workflow(client, db, ctx):
    from app.main import app

    workflow_ref_holder = {"ref": ""}

    async def _override_agent_application_service() -> AgentApplicationService:
        return AgentApplicationService(
            db=db,
            ctx=ctx,
            llm_port=QueueLLMPort(
                [
                    ChatResponse(
                        text=None,
                        tokens_prompt=1,
                        tokens_completion=1,
                        finish_reason="tool_calls",
                        tool_calls=[
                            ToolCall(
                                id="call_wf",
                                name=workflow_ref_holder["ref"],
                                arguments={"ticket_id": "TCK-3001"},
                            )
                        ],
                    ),
                    ChatResponse(text="workflow ticket processed", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
                ]
            ),
            tool_port=StubToolPort(),
            memory_service=None,
        )

    app.dependency_overrides[get_agent_application_service] = _override_agent_application_service
    try:
        headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
        workflow_response = client.post(
            "/api/v1/workflows",
            json={"name": "agent-ticket-workflow", "description": "Agent workflow binding test"},
            headers=headers,
        )
        assert workflow_response.status_code == status.HTTP_201_CREATED
        workflow_id = workflow_response.json()["data"]["id"]
        workflow_ref_holder["ref"] = f"wf:{workflow_id}"

        version_response = client.post(
            f"/api/v1/workflows/{workflow_id}/versions",
            json={
                "graph_json": {
                    "name": "agent-ticket-flow",
                    "inputs_schema": {"type": "object", "properties": {"ticket_id": {"type": "string"}}},
                    "outputs_schema": {"type": "object", "properties": {"ticket_id": {"type": "string"}}},
                    "graph": {
                        "nodes": [
                            {
                                "id": "set_ticket",
                                "type": "set_var",
                                "params": {"key": "ticket_id", "value": "{{ inputs.ticket_id }}"},
                            },
                            {
                                "id": "out1",
                                "type": "output",
                                "params": {"ticket_id": "{{ steps.set_ticket.output.value }}"},
                            },
                        ],
                        "edges": [{"id": "e1", "from": "set_ticket", "to": "out1"}],
                    },
                },
            },
            headers=headers,
        )
        assert version_response.status_code == status.HTTP_201_CREATED
        workflow_version_id = version_response.json()["data"]["id"]
        publish_workflow_response = client.post(
            f"/api/v1/workflows/{workflow_id}/publish",
            json={"version_id": workflow_version_id},
            headers=headers,
        )
        assert publish_workflow_response.status_code == status.HTTP_200_OK

        create_response = client.post(
            "/api/v1/agents",
            json={"name": "api-agent-workflow", "description": "Agent workflow API test", "visibility": "private"},
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        agent_id = create_response.json()["data"]["id"]

        agent_version_response = client.post(
            f"/api/v1/agents/{agent_id}/versions",
            json={
                "system_prompt": "Use the ticket workflow when needed.",
                "bindings": {
                    "model_ref": "model:test:primary",
                    "workflow_refs": [workflow_ref_holder["ref"]],
                },
                "verify": False,
            },
            headers=headers,
        )
        assert agent_version_response.status_code == status.HTTP_201_CREATED
        agent_version_id = agent_version_response.json()["data"]["id"]
        publish_agent_response = client.post(
            f"/api/v1/agents/{agent_id}/publish",
            json={"version_id": agent_version_id},
            headers=headers,
        )
        assert publish_agent_response.status_code == status.HTTP_200_OK

        execute_response = client.post(
            f"/api/v1/agents/{agent_id}/execute",
            json={"input": "Process ticket TCK-3001"},
            headers=headers,
        )
        assert execute_response.status_code == status.HTTP_200_OK
        payload = execute_response.json()["data"]
        assert payload["output"] == "workflow ticket processed"
        assert payload["tool_calls"] == 1

        detail_response = client.get(
            f"/api/v1/responses/{payload['response_id']}/detail",
            headers=headers,
        )
        assert detail_response.status_code == status.HTTP_200_OK
        detail_payload = detail_response.json()["data"]
        tool_call = detail_payload["tool_calls"][0]
        assert tool_call["tool_name"] == workflow_ref_holder["ref"]
        assert tool_call["tool_type"] == "workflow"
        assert tool_call["status"] == "completed"
        assert tool_call["result_json"]["result"]["workflow_run_id"].startswith("run_")
        assert tool_call["result_json"]["result"]["output"]["ticket_id"] == "TCK-3001"
    finally:
        app.dependency_overrides.pop(get_agent_application_service, None)


def test_agent_api_enterprise_demo_smoke_links_knowledge_tool_workflow_response_and_run_detail(client, db, ctx, monkeypatch):
    """Enterprise demo path should link knowledge citations, external tool calls, workflow calls, and run detail."""
    from app.main import app

    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    workflow_ref_holder = {"ref": ""}

    async def fake_knowledge_query(**kwargs):
        assert kwargs["knowledge_id"] == "kb_support"
        return {
            "results": [
                {
                    "chunk_id": "chunk_refund_1",
                    "document_id": "doc_refund",
                    "score": 0.93,
                    "text": "Refund tickets require account verification before workflow escalation.",
                    "metadata": {},
                }
            ],
            "total": 1,
            "citations": [
                {
                    "chunk_id": "chunk_refund_1",
                    "document_id": "doc_refund",
                    "rank": 1,
                    "score": 0.93,
                    "doc_key": "refund-policy.md",
                    "title": "Refund Policy",
                    "chunk_no": 2,
                    "snippet": "Refund tickets require account verification before workflow escalation.",
                }
            ],
        }

    async def _override_agent_application_service() -> AgentApplicationService:
        return AgentApplicationService(
            db=db,
            ctx=ctx,
            llm_port=QueueLLMPort(
                [
                    ChatResponse(
                        text=None,
                        tokens_prompt=3,
                        tokens_completion=2,
                        finish_reason="tool_calls",
                        tool_calls=[
                            ToolCall(
                                id="call_ticket_lookup",
                                name="tool:test:ticket_lookup",
                                arguments={"ticket_id": "TCK-DEMO-1"},
                            )
                        ],
                    ),
                    ChatResponse(
                        text=None,
                        tokens_prompt=3,
                        tokens_completion=2,
                        finish_reason="tool_calls",
                        tool_calls=[
                            ToolCall(
                                id="call_ticket_workflow",
                                name=workflow_ref_holder["ref"],
                                arguments={"ticket_id": "TCK-DEMO-1", "priority": "high"},
                            )
                        ],
                    ),
                    ChatResponse(
                        text="Verified the account and processed ticket TCK-DEMO-1.",
                        tokens_prompt=4,
                        tokens_completion=5,
                        finish_reason="stop",
                    ),
                ]
            ),
            tool_port=ToolPolicyGateway(
                gateway=StubToolPort(),
                ctx=ctx,
                trace_writer=TraceWriter(db, ctx),
                enable_egress_check=False,
            ),
            memory_service=None,
        )

    monkeypatch.setattr("app.modules.knowledge.runtime.tool_entrypoint.knowledge_query", fake_knowledge_query)
    app.dependency_overrides[get_agent_application_service] = _override_agent_application_service
    try:
        workflow_response = client.post(
            "/api/v1/workflows",
            json={"name": "enterprise-ticket-workflow", "description": "Enterprise demo ticket workflow"},
            headers=headers,
        )
        assert workflow_response.status_code == status.HTTP_201_CREATED
        workflow_id = workflow_response.json()["data"]["id"]
        workflow_ref_holder["ref"] = f"wf:{workflow_id}"

        version_response = client.post(
            f"/api/v1/workflows/{workflow_id}/versions",
            json={
                "graph_json": {
                    "name": "enterprise-ticket-flow",
                    "inputs_schema": {
                        "type": "object",
                        "properties": {
                            "ticket_id": {"type": "string"},
                            "priority": {"type": "string"},
                        },
                    },
                    "outputs_schema": {
                        "type": "object",
                        "properties": {
                            "ticket_id": {"type": "string"},
                            "priority": {"type": "string"},
                        },
                    },
                    "graph": {
                        "nodes": [
                            {
                                "id": "set_ticket",
                                "type": "set_var",
                                "params": {"set": {"ticket_id": "{{ inputs.ticket_id }}", "priority": "{{ inputs.priority }}"}},
                            },
                            {
                                "id": "out1",
                                "type": "output",
                                "params": {
                                    "ticket_id": "{{ steps.set_ticket.output.ticket_id }}",
                                    "priority": "{{ steps.set_ticket.output.priority }}",
                                },
                            },
                        ],
                        "edges": [{"id": "e1", "from": "set_ticket", "to": "out1"}],
                    },
                },
            },
            headers=headers,
        )
        assert version_response.status_code == status.HTTP_201_CREATED
        workflow_version_id = version_response.json()["data"]["id"]
        publish_workflow_response = client.post(
            f"/api/v1/workflows/{workflow_id}/publish",
            json={"version_id": workflow_version_id},
            headers=headers,
        )
        assert publish_workflow_response.status_code == status.HTTP_200_OK

        create_response = client.post(
            "/api/v1/agents",
            json={
                "name": "enterprise-demo-agent",
                "description": "Enterprise demo agent smoke test",
                "visibility": "private",
            },
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        agent_id = create_response.json()["data"]["id"]

        agent_version_response = client.post(
            f"/api/v1/agents/{agent_id}/versions",
            json={
                "system_prompt": "Use enterprise knowledge, then process the ticket workflow.",
                    "bindings": {
                        "model_ref": "model:test:primary",
                        "knowledge_refs": ["knowledge:kb_support"],
                        "tool_refs": ["tool:test:ticket_lookup"],
                        "workflow_refs": [workflow_ref_holder["ref"]],
                    },
                "verify": False,
            },
            headers=headers,
        )
        assert agent_version_response.status_code == status.HTTP_201_CREATED
        agent_version_id = agent_version_response.json()["data"]["id"]
        publish_agent_response = client.post(
            f"/api/v1/agents/{agent_id}/publish",
            json={"version_id": agent_version_id},
            headers=headers,
        )
        assert publish_agent_response.status_code == status.HTTP_200_OK

        execute_response = client.post(
            f"/api/v1/agents/{agent_id}/execute",
            json={"input": "Handle refund ticket TCK-DEMO-1"},
            headers=headers,
        )
        assert execute_response.status_code == status.HTTP_200_OK
        payload = execute_response.json()["data"]
        assert payload["output"] == "Verified the account and processed ticket TCK-DEMO-1."
        assert payload["tool_calls"] == 2
        assert payload["citations"][0]["knowledge_id"] == "kb_support"
        assert payload["citations"][0]["doc_key"] == "refund-policy.md"

        messages = ThreadRepository(db, ctx).list_messages(payload["thread_id"])
        assistant_message = next(message for message in messages if message.role == "assistant" and message.run_id == payload["run_id"])
        persisted_tool_calls = assistant_message.tool_calls_json
        assert len(persisted_tool_calls) == 2
        assert {item["tool_name"] for item in persisted_tool_calls} == {
            "tool:test:ticket_lookup",
            workflow_ref_holder["ref"],
        }
        assert assistant_message.metadata_json["tool_calls"] == persisted_tool_calls
        assert assistant_message.metadata_json["tool_calls_count"] == 2

        response_detail = client.get(
            f"/api/v1/responses/{payload['response_id']}/detail",
            headers=headers,
        )
        assert response_detail.status_code == status.HTTP_200_OK
        detail_payload = response_detail.json()["data"]
        assert detail_payload["response"]["output_json"]["citations"] == payload["citations"]
        assert detail_payload["response"]["usage_json"]["budget_exceeded"] is False
        tool_calls = {item["tool_name"]: item for item in detail_payload["tool_calls"]}
        external_tool_call = tool_calls["tool:test:ticket_lookup"]
        assert external_tool_call["run_step_tool_call_id"]
        assert external_tool_call["tool_call_id"] == "call_ticket_lookup"
        assert external_tool_call["attempt_count"] == 1
        assert external_tool_call["tool_type"] == "builtin"
        assert external_tool_call["status"] == "completed"
        assert external_tool_call["arguments_json"] == {"ticket_id": "TCK-DEMO-1"}
        assert external_tool_call["result_json"]["result"]["tool_ref"] == "tool:test:ticket_lookup"
        assert external_tool_call["result_json"]["result"]["parameters"] == {"ticket_id": "TCK-DEMO-1"}

        workflow_tool_call = tool_calls[workflow_ref_holder["ref"]]
        assert workflow_tool_call["run_step_tool_call_id"]
        assert workflow_tool_call["tool_call_id"] == "call_ticket_workflow"
        assert workflow_tool_call["attempt_count"] == 1
        assert workflow_tool_call["tool_type"] == "workflow"
        assert workflow_tool_call["status"] == "completed"
        assert workflow_tool_call["result_json"]["result"]["workflow_run_id"].startswith("run_")
        assert workflow_tool_call["result_json"]["result"]["output"] == {
            "ticket_id": "TCK-DEMO-1",
            "priority": "high",
        }
        durable_tool_calls = db.execute(
            select(RunStepToolCall).where(
                RunStepToolCall.run_id == payload["run_id"]
            )
        ).scalars().all()
        assert {item.tool_ref for item in durable_tool_calls} == {
            "tool:test:ticket_lookup",
            workflow_ref_holder["ref"],
        }
        assert all(item.status == "succeeded" for item in durable_tool_calls)
        event_types = [item["type"] for item in detail_payload["events"]]
        assert "tool.call.completed" in event_types
        assert "response.output_text.done" in event_types

        run_detail = client.get(
            f"/api/v1/runs/{payload['run_id']}",
            params={"include_steps": True, "include_cost": True, "include_artifacts": True},
            headers=headers,
        )
        assert run_detail.status_code == status.HTTP_200_OK
        run_payload = run_detail.json()["data"]
        assert run_payload["run"]["status"] == "succeeded"
        assert run_payload["usage_summary"]["tokens_prompt"] >= payload["tokens_prompt"]
        assert run_payload["usage_summary"]["tokens_completion"] >= payload["tokens_completion"]
        retrieval_steps = [step for step in run_payload["steps"] if step["step_type"] == "retrieval"]
        assert retrieval_steps
        assert retrieval_steps[0]["status"] == "succeeded"
        assert retrieval_steps[0]["metrics_json"]["citation_count"] == 1
    finally:
        app.dependency_overrides.pop(get_agent_application_service, None)


def test_agent_api_rejects_client_supplied_attachment_history(client, db, ctx):
    from app.main import app

    llm_port = QueueLLMPort(
        [
            ChatResponse(text="attachment processed", tokens_prompt=1, tokens_completion=1, finish_reason="stop"),
        ]
    )

    async def _override_agent_application_service() -> AgentApplicationService:
        return AgentApplicationService(
            db=db,
            ctx=ctx,
            llm_port=llm_port,
            tool_port=StubToolPort(),
            memory_service=None,
        )

    app.dependency_overrides[get_agent_application_service] = _override_agent_application_service
    try:
        headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
        create_response = client.post(
            "/api/v1/agents",
            json={"name": "api-agent-attachments", "description": "Agent attachment API test", "visibility": "private"},
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        agent_id = create_response.json()["data"]["id"]

        version_response = client.post(
            f"/api/v1/agents/{agent_id}/versions",
            json={
                "system_prompt": "Use supplied attachment context.",
                "bindings": {"model_ref": "model:test:primary"},
                "verify": False,
            },
            headers=headers,
        )
        assert version_response.status_code == status.HTTP_201_CREATED
        version_id = version_response.json()["data"]["id"]
        publish_response = client.post(
            f"/api/v1/agents/{agent_id}/publish",
            json={"version_id": version_id},
            headers=headers,
        )
        assert publish_response.status_code == status.HTTP_200_OK

        execute_response = client.post(
            f"/api/v1/agents/{agent_id}/execute",
            json={
                "input": "Summarize the attached support notes",
                "attachments": [{"id": "att_support"}],
            },
            headers=headers,
        )
        assert execute_response.status_code == status.HTTP_400_BAD_REQUEST
        assert llm_port.messages == []
    finally:
        app.dependency_overrides.pop(get_agent_application_service, None)


def test_agent_api_persists_budget_status_in_response_usage(client, db, ctx):
    from app.main import app

    async def _override_agent_application_service() -> AgentApplicationService:
        return AgentApplicationService(
            db=db,
            ctx=ctx,
            llm_port=QueueLLMPort(
                [
                    ChatResponse(
                        text=None,
                        tokens_prompt=1,
                        tokens_completion=1,
                        finish_reason="tool_calls",
                        tool_calls=[ToolCall(id="call_1", name="tool:test:echo", arguments={"value": "blocked"})],
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
                "name": "api-agent-budget",
                "description": "Agent API budget test",
                "visibility": "private",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        agent_id = create_response.json()["data"]["id"]

        version_response = client.post(
            f"/api/v1/agents/{agent_id}/versions",
            json={
                "system_prompt": "Respect budgets.",
                "bindings": {
                    "model_ref": "model:test:primary",
                    "tool_refs": ["tool:test:echo"],
                },
                "max_tool_calls": 0,
                "verify": False,
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
            json={"input": "Use a tool"},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert execute_response.status_code == status.HTTP_200_OK
        payload = execute_response.json()["data"]
        assert payload["budget_exceeded"] is True
        assert payload["budget_reason"] == "tool_budget_exceeded"
        assert payload["tool_calls"] == 0

        detail_response = client.get(
            f"/api/v1/responses/{payload['response_id']}/detail",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert detail_response.status_code == status.HTTP_200_OK
        usage = detail_response.json()["data"]["response"]["usage_json"]
        assert usage["budget_exceeded"] is True
        assert usage["budget_reason"] == "tool_budget_exceeded"
    finally:
        app.dependency_overrides.pop(get_agent_application_service, None)


def test_agent_api_persists_failed_assistant_message_for_chat_history(client, db, ctx):
    from app.main import app

    async def _override_agent_application_service() -> AgentApplicationService:
        return AgentApplicationService(
            db=db,
            ctx=ctx,
            llm_port=FailingLLMPort(),
            tool_port=StubToolPort(),
            memory_service=None,
        )

    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    app.dependency_overrides[get_agent_application_service] = _override_agent_application_service
    try:
        create_response = client.post(
            "/api/v1/agents",
            json={"name": "api-agent-failure", "description": "Agent failure persistence test", "visibility": "private"},
            headers=headers,
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        agent_id = create_response.json()["data"]["id"]

        version_response = client.post(
            f"/api/v1/agents/{agent_id}/versions",
            json={
                "system_prompt": "Fail clearly.",
                "bindings": {"model_ref": "model:test:primary"},
                "verify": False,
            },
            headers=headers,
        )
        assert version_response.status_code == status.HTTP_201_CREATED
        version_id = version_response.json()["data"]["id"]

        publish_response = client.post(
            f"/api/v1/agents/{agent_id}/publish",
            json={"version_id": version_id},
            headers=headers,
        )
        assert publish_response.status_code == status.HTTP_200_OK

        execute_response = client.post(
            f"/api/v1/agents/{agent_id}/execute",
            json={"input": "Trigger a failure"},
            headers=headers,
        )
        assert execute_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        thread = ThreadRepository(db, ctx).list_threads(agent_id=agent_id)[0]
        messages = ThreadRepository(db, ctx).list_messages(thread.id)
        assistant_message = next(message for message in messages if message.role == "assistant")
        assert assistant_message.status == "failed"
        assert assistant_message.content == "Agent execution failed"
        assert assistant_message.error_code == "agent_execution_failed"
        assert assistant_message.error_message == "Agent execution failed"
        assert assistant_message.finish_reason == "agent_execution_failed"
        assert assistant_message.run_id == thread.latest_run_id
        assert assistant_message.response_id
        assert assistant_message.metadata_json["error_code"] == "agent_execution_failed"
        assert assistant_message.metadata_json["error_message"] == "Agent execution failed"
        assert assistant_message.metadata_json["tool_calls_count"] == 0

        thread_response = client.get(f"/api/v1/threads/{thread.id}", headers=headers)
        assert thread_response.status_code == status.HTTP_200_OK
        api_assistant_message = next(
            message for message in thread_response.json()["data"]["messages"] if message["role"] == "assistant"
        )
        assert api_assistant_message["status"] == "failed"
        assert api_assistant_message["content"] == "Agent execution failed"
        assert api_assistant_message["error_code"] == "agent_execution_failed"
        assert api_assistant_message["error_message"] == "Agent execution failed"
        assert api_assistant_message["finish_reason"] == "agent_execution_failed"
        assert api_assistant_message["run_id"] == thread.latest_run_id
        assert api_assistant_message["response_id"] == assistant_message.response_id
        assert api_assistant_message["metadata_json"]["error_code"] == "agent_execution_failed"
        assert api_assistant_message["metadata_json"]["error_message"] == "Agent execution failed"
    finally:
        app.dependency_overrides.pop(get_agent_application_service, None)


def test_agent_api_accepts_mcp_tool_refs_via_tool_refs(client, db, ctx):
    from app.main import app

    async def _override_agent_application_service() -> AgentApplicationService:
        return AgentApplicationService(
            db=db,
            ctx=ctx,
            llm_port=QueueLLMPort([]),
            tool_port=StubToolPort(),
            memory_service=None,
        )

    app.dependency_overrides[get_agent_application_service] = _override_agent_application_service
    try:
        create_response = client.post(
            "/api/v1/agents",
            json={
                "name": "api-agent-invalid-mcp",
                "description": "Agent API invalid MCP test",
                "visibility": "private",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        agent_id = create_response.json()["data"]["id"]

        version_response = client.post(
            f"/api/v1/agents/{agent_id}/versions",
            json={
                "system_prompt": "Use tools carefully.",
                "bindings": {
                    "model_ref": "model:test:primary",
                    "tool_refs": ["mcp_tool:missing:list_prs"],
                },
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
        bindings = bindings_response.json()["data"]
        assert any(binding["binding_type"] == "tool" and binding["target_key"] == "mcp_tool:missing:list_prs" for binding in bindings)
        assert version_id
    finally:
        app.dependency_overrides.pop(get_agent_application_service, None)


def test_agent_api_publish_and_rollback_keep_head_and_live_separate(client, db, ctx):
    from app.main import app

    async def _override_agent_application_service() -> AgentApplicationService:
        return AgentApplicationService(
            db=db,
            ctx=ctx,
            llm_port=QueueLLMPort([]),
            tool_port=StubToolPort(),
            memory_service=None,
        )

    app.dependency_overrides[get_agent_application_service] = _override_agent_application_service
    try:
        create_response = client.post(
            "/api/v1/agents",
            json={
                "name": "api-agent-rollback",
                "description": "Agent rollback API test",
                "visibility": "private",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        agent_id = create_response.json()["data"]["id"]

        version1 = client.post(
            f"/api/v1/agents/{agent_id}/versions",
            json={
                "system_prompt": "v1",
                "bindings": {"model_ref": "model:test:primary"},
                "verify": True,
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert version1.status_code == status.HTTP_201_CREATED
        version1_id = version1.json()["data"]["id"]

        publish1 = client.post(
            f"/api/v1/agents/{agent_id}/publish",
            json={"version_id": version1_id, "notes": "publish v1"},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert publish1.status_code == status.HTTP_200_OK

        version2 = client.post(
            f"/api/v1/agents/{agent_id}/versions",
            json={
                "system_prompt": "v2",
                "bindings": {"model_ref": "model:test:primary"},
                "verify": True,
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert version2.status_code == status.HTTP_201_CREATED
        version2_id = version2.json()["data"]["id"]

        publish2 = client.post(
            f"/api/v1/agents/{agent_id}/publish",
            json={"version_id": version2_id, "notes": "publish v2"},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert publish2.status_code == status.HTTP_200_OK

        rollback = client.post(
            f"/api/v1/agents/{agent_id}/rollback",
            json={"version_id": version1_id, "notes": "rollback v1"},
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert rollback.status_code == status.HTTP_200_OK
        payload = rollback.json()["data"]
        assert payload["current_version_id"] == version2_id
        assert payload["published_version_id"] == version1_id

        releases = client.get(
            f"/api/v1/agents/{agent_id}/releases",
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert releases.status_code == status.HTTP_200_OK
        release_items = releases.json()["data"]["items"]
        assert len(release_items) == 3
        assert release_items[0]["action"] == "rollback"
        assert release_items[0]["from_version_id"] == version2_id
        assert release_items[0]["to_version_id"] == version1_id
        assert release_items[0]["notes"] == "rollback v1"
        assert release_items[1]["action"] == "publish"
        assert release_items[1]["from_version_id"] == version1_id
        assert release_items[1]["to_version_id"] == version2_id
        assert release_items[1]["notes"] == "publish v2"
    finally:
        app.dependency_overrides.pop(get_agent_application_service, None)


def test_agent_api_execute_rejects_forbidden_override_fields(client, db, ctx):
    from app.main import app

    async def _override_agent_application_service() -> AgentApplicationService:
        return AgentApplicationService(
            db=db,
            ctx=ctx,
            llm_port=QueueLLMPort([]),
            tool_port=StubToolPort(),
            memory_service=None,
        )

    app.dependency_overrides[get_agent_application_service] = _override_agent_application_service
    try:
        create_response = client.post(
            "/api/v1/agents",
            json={
                "name": "api-agent-execute-contract",
                "description": "Agent API execute contract test",
                "visibility": "private",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        agent_id = create_response.json()["data"]["id"]

        version_response = client.post(
            f"/api/v1/agents/{agent_id}/versions",
            json={
                "system_prompt": "You are precise.",
                "bindings": {"model_ref": "model:test:primary"},
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
                "input": "Execute now",
                "model": "model:test:override",
            },
            headers={"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"},
        )
        assert execute_response.status_code == status.HTTP_400_BAD_REQUEST
    finally:
        app.dependency_overrides.pop(get_agent_application_service, None)
