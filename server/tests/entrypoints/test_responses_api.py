"""Entry-point tests for the Responses API."""

import asyncio
import json

from fastapi import status

from app.adapters.agui.responses import AgUiInteractionProtocolAdapter
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.responses.repository import (
    ResponseEventRepository,
    ResponseRepository,
)
from app.kernel.runtime.responses.service import ResponseService
from app.kernel.runtime.runs.writer import TraceWriter


def _agui_run_input(*, thread_id: str, run_id: str, content: str) -> dict:
    return {
        "threadId": thread_id,
        "runId": run_id,
        "state": {},
        "messages": [
            {
                "id": f"msg_{run_id}",
                "role": "user",
                "content": content,
            }
        ],
        "tools": [],
        "context": [],
        "forwardedProps": {
            "soit": {
                "mode": "direct",
                "modelRef": "model:openai:gpt-5.1",
            }
        },
    }


def _agui_agent_run_input(*, thread_id: str, run_id: str, agent_id: str, content: str) -> dict:
    payload = _agui_run_input(thread_id=thread_id, run_id=run_id, content=content)
    payload["forwardedProps"]["soit"] = {
        "mode": "agent",
        "agentId": agent_id,
    }
    return payload


def _parse_agui_sse(body: str) -> tuple[list[str], list[dict]]:
    event_ids: list[str] = []
    events: list[dict] = []
    for raw_line in body.splitlines():
        if raw_line.startswith("id: "):
            event_ids.append(raw_line[4:])
        elif raw_line.startswith("data: "):
            payload = raw_line[6:]
            if payload != "[DONE]":
                events.append(json.loads(payload))
    return event_ids, events


def _stream_agui_response(client, *, headers: dict, payload: dict) -> tuple[list[str], list[dict]]:
    with client.stream(
        "POST",
        "/api/v1/responses",
        json=payload,
        headers=headers,
    ) as response:
        assert response.status_code == status.HTTP_200_OK
        body = response.read().decode("utf-8")
    return _parse_agui_sse(body)


def test_responses_api_accepts_agui_run_input_and_streams_standard_events(client):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    thread_response = client.post(
        "/api/v1/threads",
        json={"title": "AG-UI contract"},
        headers=headers,
    )
    assert thread_response.status_code == status.HTTP_201_CREATED
    thread_id = thread_response.json()["data"]["id"]

    with client.stream(
        "POST",
        "/api/v1/responses",
        json=_agui_run_input(
            thread_id=thread_id,
            run_id="interaction_contract_1",
            content="hello ag-ui",
        ),
        headers=headers,
    ) as response:
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.read().decode("utf-8")

    event_ids, events = _parse_agui_sse(body)
    event_types = [event["type"] for event in events]

    assert event_types[0] == "RUN_STARTED"
    assert "TEXT_MESSAGE_START" in event_types
    assert "TEXT_MESSAGE_CONTENT" in event_types
    assert "TEXT_MESSAGE_END" in event_types
    assert event_types[-1] == "RUN_FINISHED"
    assert events[0]["threadId"] == thread_id
    assert events[0]["runId"] == "interaction_contract_1"

    resources_event = next(
        event
        for event in events
        if event["type"] == "CUSTOM" and event["name"] == "soit.resources"
    )
    assert resources_event["value"]["responseId"].startswith("resp_")
    assert resources_event["value"]["executionRunId"].startswith("run_")
    assert event_ids == [
        f"{resources_event['value']['responseId']}:{sequence}"
        for sequence in range(1, len(event_ids) + 1)
    ]


def test_agui_request_resolves_governed_attachments_into_the_thread_ledger(client):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    uploaded = client.post(
        "/api/v1/attachments",
        files={"file": ("context.txt", b"governed attachment context", "text/plain")},
        headers=headers,
    )
    attachment_id = uploaded.json()["data"]["id"]
    thread_response = client.post(
        "/api/v1/threads",
        json={"title": "AG-UI governed attachment"},
        headers=headers,
    )
    thread_id = thread_response.json()["data"]["id"]
    payload = _agui_run_input(
        thread_id=thread_id,
        run_id="interaction_attachment_contract",
        content="Summarize the attachment",
    )
    payload["forwardedProps"]["soit"]["attachmentIds"] = [attachment_id]

    _, events = _stream_agui_response(client, headers=headers, payload=payload)

    assert events[-1]["type"] == "RUN_FINISHED"
    detail = client.get(f"/api/v1/threads/{thread_id}", headers=headers)
    user_message = detail.json()["data"]["messages"][0]
    assert user_message["attachments_json"] == [
        {
            "id": attachment_id,
            "name": "context.txt",
            "filename": "context.txt",
            "type": "document",
            "content_type": "text/plain",
            "size": len(b"governed attachment context"),
            "checksum": uploaded.json()["data"]["checksum"],
        }
    ]
    assert "governed attachment context" not in str(user_message["metadata_json"])


def test_agui_regenerate_creates_an_assistant_branch_without_duplicating_the_user(client):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    thread_response = client.post(
        "/api/v1/threads",
        json={"title": "AG-UI regenerate branch"},
        headers=headers,
    )
    thread_id = thread_response.json()["data"]["id"]
    _, first_events = _stream_agui_response(
        client,
        headers=headers,
        payload=_agui_run_input(
            thread_id=thread_id,
            run_id="interaction_branch_first",
            content="Give me two alternatives",
        ),
    )
    first_detail = client.get(f"/api/v1/threads/{thread_id}", headers=headers).json()["data"]
    user = first_detail["messages"][0]

    regenerate_payload = _agui_run_input(
        thread_id=thread_id,
        run_id="interaction_branch_regenerate",
        content=user["content"],
    )
    regenerate_payload["messages"][0]["id"] = user["id"]
    _, second_events = _stream_agui_response(
        client,
        headers=headers,
        payload=regenerate_payload,
    )

    detail = client.get(f"/api/v1/threads/{thread_id}", headers=headers).json()["data"]
    users = [message for message in detail["messages"] if message["role"] == "user"]
    assistants = [message for message in detail["messages"] if message["role"] == "assistant"]
    assert [message["id"] for message in users] == [user["id"]]
    assert len(assistants) == 2
    assert {message["parent_message_id"] for message in assistants} == {user["id"]}
    first_response_id = next(
        event["value"]["responseId"] for event in first_events if event.get("name") == "soit.resources"
    )
    second_response_id = next(
        event["value"]["responseId"] for event in second_events if event.get("name") == "soit.resources"
    )
    first_response = client.get(f"/api/v1/responses/{first_response_id}", headers=headers).json()["data"]
    second_response = client.get(f"/api/v1/responses/{second_response_id}", headers=headers).json()["data"]
    assert first_response["metadata_json"]["branch_id"]
    assert second_response["metadata_json"]["branch_id"] == first_response["metadata_json"]["branch_id"]


def test_agui_direct_mode_uses_the_detached_interaction_executor(client):
    from app.api.v1.responses.dependencies import get_response_interaction_executor
    from app.main import app

    calls: list[dict] = []

    async def execute_interaction(
        payload,
        *,
        interaction_id,
        parent_interaction_id,
        protocol,
    ):
        calls.append(
            {
                "interaction_id": interaction_id,
                "parent_interaction_id": parent_interaction_id,
                "protocol": protocol.source,
                "thread_id": payload.thread_id,
            }
        )
        yield {
            "id": "resp_detached:1",
            "data": {
                "type": "RUN_STARTED",
                "threadId": payload.thread_id,
                "runId": interaction_id,
            },
        }
        yield {
            "id": "resp_detached:2",
            "data": {
                "type": "RUN_FINISHED",
                "threadId": payload.thread_id,
                "runId": interaction_id,
            },
        }

    app.dependency_overrides[get_response_interaction_executor] = lambda: execute_interaction
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    try:
        thread_response = client.post(
            "/api/v1/threads",
            json={"title": "Detached AG-UI direct contract"},
            headers=headers,
        )
        thread_id = thread_response.json()["data"]["id"]
        event_ids, events = _stream_agui_response(
            client,
            headers=headers,
            payload=_agui_run_input(
                thread_id=thread_id,
                run_id="interaction_detached_direct",
                content="run detached",
            ),
        )
    finally:
        app.dependency_overrides.pop(get_response_interaction_executor, None)

    assert calls == [
        {
            "interaction_id": "interaction_detached_direct",
            "parent_interaction_id": None,
            "protocol": "ag-ui",
            "thread_id": thread_id,
        }
    ]
    assert event_ids == ["resp_detached:1", "resp_detached:2"]
    assert [event["type"] for event in events] == ["RUN_STARTED", "RUN_FINISHED"]


def test_agui_events_persist_envelope_and_replay_after_sequence(client):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    thread_response = client.post(
        "/api/v1/threads",
        json={"title": "AG-UI replay"},
        headers=headers,
    )
    thread_id = thread_response.json()["data"]["id"]
    event_ids, live_events = _stream_agui_response(
        client,
        headers=headers,
        payload=_agui_run_input(
            thread_id=thread_id,
            run_id="interaction_replay_1",
            content="replay ag-ui",
        ),
    )
    resources_event = next(event for event in live_events if event.get("name") == "soit.resources")
    response_id = resources_event["value"]["responseId"]

    events_response = client.get(
        f"/api/v1/responses/{response_id}/events",
        params={"after_sequence": 3, "page_size": 100},
        headers=headers,
    )
    assert events_response.status_code == status.HTTP_200_OK
    stored_events = events_response.json()["data"]["items"]
    assert stored_events
    assert all(event["sequence"] > 3 for event in stored_events)
    assert all(event["protocol_version"] == "ag-ui/0.1.19" for event in stored_events)
    assert all(event["interaction_id"] == "interaction_replay_1" for event in stored_events)
    assert all(event["visibility"] == "user" for event in stored_events)

    replay_response = client.get(
        f"/api/v1/responses/{response_id}/stream",
        params={"after_sequence": 3},
        headers=headers,
    )
    assert replay_response.status_code == status.HTTP_200_OK
    replay_ids, replay_events = _parse_agui_sse(replay_response.text)
    assert replay_ids == event_ids[3:]
    assert replay_events == live_events[3:]

    header_replay_response = client.get(
        f"/api/v1/responses/{response_id}/stream",
        headers={**headers, "Last-Event-ID": event_ids[2]},
    )
    assert header_replay_response.status_code == status.HTTP_200_OK
    header_replay_ids, header_replay_events = _parse_agui_sse(header_replay_response.text)
    assert header_replay_ids == event_ids[3:]
    assert header_replay_events == live_events[3:]


def test_agui_interaction_id_is_idempotent(client):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    thread_response = client.post(
        "/api/v1/threads",
        json={"title": "AG-UI idempotency"},
        headers=headers,
    )
    thread_id = thread_response.json()["data"]["id"]
    payload = _agui_run_input(
        thread_id=thread_id,
        run_id="interaction_idempotent_1",
        content="run once",
    )

    _, first_events = _stream_agui_response(client, headers=headers, payload=payload)
    _, second_events = _stream_agui_response(client, headers=headers, payload=payload)
    first_resources = next(event for event in first_events if event.get("name") == "soit.resources")
    second_resources = next(event for event in second_events if event.get("name") == "soit.resources")

    assert second_resources["value"]["responseId"] == first_resources["value"]["responseId"]
    assert second_resources["value"]["executionRunId"] == first_resources["value"]["executionRunId"]
    assert second_events == first_events


def test_agui_interaction_id_rejects_a_different_request_before_streaming(client):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    thread_response = client.post(
        "/api/v1/threads",
        json={"title": "AG-UI conflict"},
        headers=headers,
    )
    thread_id = thread_response.json()["data"]["id"]
    run_id = "interaction_conflict_1"
    _stream_agui_response(
        client,
        headers=headers,
        payload=_agui_run_input(thread_id=thread_id, run_id=run_id, content="first"),
    )

    response = client.post(
        "/api/v1/responses",
        json=_agui_run_input(thread_id=thread_id, run_id=run_id, content="different"),
        headers=headers,
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["code"] == "CONFLICT"


def test_agui_interaction_id_is_scoped_by_tenant_and_workspace(client):
    from app.main import app
    from app.middleware.auth import get_current_context

    run_id = "interaction_scoped_1"
    resource_ids: list[str] = []

    def context_override(context: RequestContext):
        async def override_context() -> RequestContext:
            return context

        return override_context

    for tenant_id, workspace_id in (
        ("tenant-a", "workspace-a"),
        ("tenant-b", "workspace-a"),
        ("tenant-a", "workspace-b"),
    ):
        current_context = RequestContext(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            user_id="test-user",
            tenant_role="Owner",
            workspace_role="Owner",
        )
        app.dependency_overrides[get_current_context] = context_override(current_context)
        headers = {"X-Tenant-Id": tenant_id, "X-Workspace-Id": workspace_id}
        thread_response = client.post(
            "/api/v1/threads",
            json={"title": "AG-UI scoped interaction"},
            headers=headers,
        )
        assert thread_response.status_code == status.HTTP_201_CREATED
        thread_id = thread_response.json()["data"]["id"]
        _, events = _stream_agui_response(
            client,
            headers=headers,
            payload=_agui_run_input(
                thread_id=thread_id,
                run_id=run_id,
                content=f"{tenant_id}/{workspace_id}",
            ),
        )
        resources = next(event for event in events if event.get("name") == "soit.resources")
        resource_ids.append(resources["value"]["responseId"])

    assert len(set(resource_ids)) == 3


def test_agui_cancel_persists_a_replayable_terminal_event(client, db, ctx):
    from app.kernel.runtime.responses.schemas import ResponseCreateRequest

    service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=TraceWriter(db, ctx),
    )
    interaction_id = "interaction_cancel_contract"
    response = service.create_response(
        ResponseCreateRequest(
            model="model:openai:gpt-5.1",
            thread_id=None,
            input={"messages": [{"role": "user", "content": "cancel me"}]},
            metadata={
                "protocol": "ag-ui",
                "protocol_version": "0.1.19",
                "interaction_id": interaction_id,
                "request_hash": "cancel-contract-hash",
            },
        ),
        emit_initial_events=False,
    )
    response = service.mark_running(response)
    service.create_interaction(
        interaction_id=interaction_id,
        parent_interaction_id=None,
        response=response,
        request_hash="cancel-contract-hash",
    )
    protocol = AgUiInteractionProtocolAdapter()
    started = protocol.text_started(message_id="msg_cancel_contract")
    service.append_event(
        response=response,
        event_type=started.type,
        payload=started.payload,
        source=protocol.source,
        protocol_version=protocol.protocol_version,
        interaction_id=interaction_id,
    )
    db.commit()

    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    first = client.post(f"/api/v1/responses/{response.id}/cancel", headers=headers)
    second = client.post(f"/api/v1/responses/{response.id}/cancel", headers=headers)

    assert first.status_code == status.HTTP_200_OK
    assert first.json()["data"]["response"]["status"] == "canceled"
    assert second.status_code == status.HTTP_200_OK
    events_response = client.get(f"/api/v1/responses/{response.id}/events", headers=headers)
    events = events_response.json()["data"]["items"]
    assert [event["type"] for event in events] == [
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_END",
        "RUN_FINISHED",
    ]
    assert events[0]["source"] == "ag-ui"
    assert events[1]["payload_json"] == {
        "type": "TEXT_MESSAGE_END",
        "messageId": "msg_cancel_contract",
    }
    assert events[2]["payload_json"] == {
        "type": "RUN_FINISHED",
        "threadId": response.thread_id or "",
        "runId": interaction_id,
        "result": {"status": "canceled", "finishReason": "cancelled"},
    }
    replay = client.get(f"/api/v1/responses/{response.id}/stream", headers=headers)
    _, replay_events = _parse_agui_sse(replay.text)
    assert replay_events == [event["payload_json"] for event in events]
    assert service.get_interaction(interaction_id).status == "canceled"


def test_agui_cancel_cancels_a_queued_approval_resume_child(client, db, ctx):
    from app.kernel.runtime.tasks.service import TaskService

    service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=TraceWriter(db, ctx),
    )
    run = service.trace_writer.create_run("agent", kind="agent")
    service.trace_writer.update_run_status(run.id, "running")
    task_service = TaskService(db, ctx)
    task = task_service.create_task(
        task_type="agent.stream",
        status="running",
        agent_id="agent_cancel_resume",
        thread_id="thread_cancel_resume",
        run_id=run.id,
    )
    response = service.create_linked_response(
        run_id=run.id,
        thread_id="thread_cancel_resume",
        task_id=task.id,
        agent_id="agent_cancel_resume",
        metadata_json={
            "protocol": "ag-ui",
            "protocol_version": "0.1.19",
            "interaction_id": "interaction_cancel_resume_parent",
        },
        emit_initial_events=False,
    )
    response = service.mark_running(response)
    parent = service.create_interaction(
        interaction_id="interaction_cancel_resume_parent",
        parent_interaction_id=None,
        response=response,
        request_hash="hash_cancel_resume_parent",
    )
    parent.status = "resuming"
    parent.resume_interaction_id = "interaction_cancel_resume_child"
    db.add(parent)
    child, _ = service.claim_interaction(
        interaction_id="interaction_cancel_resume_child",
        parent_interaction_id=parent.interaction_id,
        thread_id="thread_cancel_resume",
        request_hash="hash_cancel_resume_child",
        execution_json={"mode": "agent"},
    )
    task_service.transition_task(task_id=task.id, status="waiting_approval")
    service.trace_writer.update_run_status(run.id, "waiting_approval")
    db.commit()

    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    cancel = client.post(f"/api/v1/responses/{response.id}/cancel", headers=headers)

    assert cancel.status_code == status.HTTP_200_OK
    db.expire_all()
    assert service.get_response(response.id).status == "canceled"
    assert task_service.get_task(task.id).status == "canceled"
    assert db.get(Run, run.id).status == "canceled"
    assert service.get_interaction(parent.interaction_id).status == "canceled"
    assert service.get_interaction(child.interaction_id).status == "canceled"
    events = service.list_response_events(
        response.id,
        limit=100,
        offset=0,
        interaction_id=child.interaction_id,
    )
    assert [event.type for event in events] == ["RUN_FINISHED"]
    assert events[0].payload_json["result"]["status"] == "canceled"


def test_agui_agent_mode_uses_the_detached_agent_executor(client, db, ctx):
    from app.api.v1.agent.dependencies import get_agent_stream_executor
    from app.main import app

    async def execute_agent(
        agent_id,
        inputs,
        event_emitter,
        on_response_started=None,
        response_metadata=None,
    ):
        assert agent_id == "agent_contract"
        assert inputs["input"] == "use the time tool"
        service = ResponseService(
            db=db,
            ctx=ctx,
            response_repo=ResponseRepository(db, ctx),
            event_repo=ResponseEventRepository(db, ctx),
            trace_writer=TraceWriter(db, ctx),
        )
        response = service.create_linked_response(
            run_id="run_agent_contract",
            thread_id=inputs["thread_id"],
            task_id="task_agent_contract",
            agent_id=agent_id,
            model="model:openai:gpt-5.1",
            metadata_json=response_metadata,
            emit_initial_events=False,
        )
        response = service.mark_running(response)
        assert on_response_started is not None
        await on_response_started(response, service)
        await event_emitter("agent.plan.started", {"iteration": 1})
        await event_emitter(
            "agent.tool.started",
            {
                "tool_ref": "tool:function:time_now",
                "tool_type": "builtin",
                "tool_call_id": "call_contract",
                "arguments": {"timezone": "UTC"},
            },
        )
        await event_emitter(
            "agent.tool.succeeded",
            {
                "tool_ref": "tool:function:time_now",
                "tool_type": "builtin",
                "tool_call_id": "call_contract",
                "success": True,
                "result": {"result": "12:00"},
            },
        )
        await event_emitter("agent.response.succeeded", {"output": "It is 12:00."})
        service.complete_response(
            response=response,
            output_json={"text": "It is 12:00."},
            usage_json={"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
            output_event_type=None,
            completed_event_type=None,
        )
        return {
            "run_id": response.run_id,
            "response_id": response.id,
            "thread_id": response.thread_id,
            "task_id": response.task_id,
            "model": response.model,
            "output": "It is 12:00.",
            "tokens_prompt": 8,
            "tokens_completion": 4,
            "citations": [],
        }

    app.dependency_overrides[get_agent_stream_executor] = lambda: execute_agent
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    try:
        thread_response = client.post(
            "/api/v1/threads",
            json={"title": "AG-UI Agent contract"},
            headers=headers,
        )
        thread_id = thread_response.json()["data"]["id"]
        _, events = _stream_agui_response(
            client,
            headers=headers,
            payload=_agui_agent_run_input(
                thread_id=thread_id,
                run_id="interaction_agent_contract",
                agent_id="agent_contract",
                content="use the time tool",
            ),
        )
    finally:
        app.dependency_overrides.pop(get_agent_stream_executor, None)

    event_types = [event["type"] for event in events]
    assert event_types[0] == "RUN_STARTED"
    assert "ACTIVITY_SNAPSHOT" in event_types
    assert "TOOL_CALL_START" in event_types
    assert "TOOL_CALL_RESULT" in event_types
    assert "TEXT_MESSAGE_CONTENT" in event_types
    assert event_types[-1] == "RUN_FINISHED"
    resources = next(event for event in events if event.get("name") == "soit.resources")
    assert resources["value"]["agentId"] == "agent_contract"
    assert resources["value"]["taskId"] == "task_agent_contract"


def test_agui_agent_approval_interrupt_resumes_the_same_resources(client, db, ctx):
    from app.api.v1.agent.dependencies import get_agent_stream_executor
    from app.kernel.runtime.tasks.service import TaskService
    from app.main import app
    from app.modules.observe.application.schemas import ApprovalCreate
    from app.modules.observe.application.service import ObserveService

    interrupt_id = "approval_contract_interrupt"
    trace_writer = TraceWriter(db, ctx)
    task_service = TaskService(db, ctx)
    observe_service = ObserveService(db, ctx)
    resource_ids: dict[str, str] = {}

    async def execute_agent(
        agent_id,
        inputs,
        event_emitter,
        on_response_started=None,
        response_metadata=None,
    ):
        service = ResponseService(
            db=db,
            ctx=ctx,
            response_repo=ResponseRepository(db, ctx),
            event_repo=ResponseEventRepository(db, ctx),
            trace_writer=trace_writer,
        )
        assert on_response_started is not None
        if not inputs.get("_agui_resume"):
            run = trace_writer.create_run(
                "agent",
                kind="agent",
                subject_kind="agent",
                subject_id=agent_id,
                subject_version_id="version_approval_contract",
            )
            trace_writer.update_run_status(run.id, "running")
            task = task_service.create_task(
                task_type="agent.stream",
                status="running",
                agent_id=agent_id,
                thread_id=inputs["thread_id"],
                run_id=run.id,
            )
            response = service.create_linked_response(
                run_id=run.id,
                thread_id=inputs["thread_id"],
                task_id=task.id,
                agent_id=agent_id,
                metadata_json=response_metadata,
                emit_initial_events=False,
            )
            response = service.mark_running(response)
            await on_response_started(response, service)
            approval = await observe_service.create_approval(
                ApprovalCreate(
                    run_id=run.id,
                    task_id=task.id,
                    thread_id=inputs["thread_id"],
                    agent_id=agent_id,
                    title="Approve contract tool",
                    policy_ref="policy:contract",
                    details_json={
                        "interrupt_id": interrupt_id,
                        "tool_ref": "tool:test:contract",
                    },
                )
            )
            resource_ids.update(
                run_id=run.id,
                task_id=task.id,
                response_id=response.id,
                approval_id=approval.id,
            )
            task_service.transition_task(task_id=task.id, status="waiting_approval")
            trace_writer.update_run_status(run.id, "waiting_approval")
            interrupt = {
                "id": interrupt_id,
                "reason": "tool_call",
                "message": "Approve contract tool",
                "toolCallId": "call_contract_approval",
                "metadata": {"toolRef": "tool:test:contract"},
            }
            await event_emitter(
                "agent.approval.required",
                {"run_id": run.id, "interrupt": interrupt},
            )
            return {
                "status": "waiting_approval",
                "interrupt": interrupt,
                "run_id": run.id,
                "response_id": response.id,
                "task_id": task.id,
                "thread_id": inputs["thread_id"],
                "output": "",
                "model": "model:openai:gpt-5.1",
            }

        assert inputs["_resume_execution"] == {
            "run_id": resource_ids["run_id"],
            "task_id": resource_ids["task_id"],
            "thread_id": inputs["thread_id"],
            "agent_id": agent_id,
            "response_id": resource_ids["response_id"],
        }
        assert inputs["_agui_resume"][0]["approval_status"] == "approved"
        response = service.get_response(resource_ids["response_id"])
        task_service.resume_task(task_id=resource_ids["task_id"])
        trace_writer.update_run_status(resource_ids["run_id"], "running")
        await on_response_started(response, service)
        await event_emitter("agent.response.succeeded", {"output": "Approved and completed."})
        service.complete_response(
            response=response,
            output_json={"text": "Approved and completed."},
            output_event_type=None,
            completed_event_type=None,
        )
        task_service.transition_task(task_id=resource_ids["task_id"], status="succeeded")
        trace_writer.update_run_status(resource_ids["run_id"], "succeeded")
        return {
            "run_id": resource_ids["run_id"],
            "response_id": response.id,
            "task_id": resource_ids["task_id"],
            "thread_id": inputs["thread_id"],
            "output": "Approved and completed.",
            "model": "model:openai:gpt-5.1",
        }

    app.dependency_overrides[get_agent_stream_executor] = lambda: execute_agent
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    try:
        thread_response = client.post(
            "/api/v1/threads",
            json={"title": "AG-UI approval contract"},
            headers=headers,
        )
        thread_id = thread_response.json()["data"]["id"]
        _, interrupted_events = _stream_agui_response(
            client,
            headers=headers,
            payload=_agui_agent_run_input(
                thread_id=thread_id,
                run_id="interaction_approval_first",
                agent_id="agent_approval_contract",
                content="perform a sensitive action",
            ),
        )
        decoy_run = trace_writer.create_run(
            "agent",
            kind="agent",
            subject_kind="agent",
            subject_id="agent_approval_contract",
        )
        trace_writer.update_run_status(decoy_run.id, "running")
        trace_writer.update_run_status(decoy_run.id, "waiting_approval")
        decoy_task = task_service.create_task(
            task_type="agent.stream",
            status="waiting_approval",
            agent_id="agent_approval_contract",
            thread_id=thread_id,
            run_id=decoy_run.id,
        )
        response_service = ResponseService(
            db=db,
            ctx=ctx,
            response_repo=ResponseRepository(db, ctx),
            event_repo=ResponseEventRepository(db, ctx),
            trace_writer=trace_writer,
        )
        decoy_response = response_service.create_linked_response(
            run_id=decoy_run.id,
            thread_id=thread_id,
            task_id=decoy_task.id,
            agent_id="agent_approval_contract",
            emit_initial_events=False,
        )
        response_service.mark_running(decoy_response)
        decoy_approval = asyncio.run(
            observe_service.create_approval(
                ApprovalCreate(
                    run_id=decoy_run.id,
                    task_id=decoy_task.id,
                    thread_id=thread_id,
                    agent_id="agent_approval_contract",
                    title="Decoy approval with the same interrupt",
                    details_json={"interrupt_id": interrupt_id},
                )
            )
        )
        db.commit()
        resume_payload = _agui_agent_run_input(
            thread_id=thread_id,
            run_id="interaction_approval_resume",
            agent_id="agent_approval_contract",
            content="perform a sensitive action",
        )
        resume_payload["parentRunId"] = "interaction_approval_first"
        resume_payload["resume"] = [
            {
                "interruptId": interrupt_id,
                "status": "resolved",
                "payload": {"decision": "approved"},
            }
        ]
        _, resumed_events = _stream_agui_response(
            client,
            headers=headers,
            payload=resume_payload,
        )
    finally:
        app.dependency_overrides.pop(get_agent_stream_executor, None)

    interrupted_terminal = interrupted_events[-1]
    assert interrupted_terminal["type"] == "RUN_FINISHED"
    assert interrupted_terminal["outcome"]["type"] == "interrupt"
    assert interrupted_terminal["outcome"]["interrupts"][0]["id"] == interrupt_id
    resumed_resources = next(
        event for event in resumed_events if event.get("name") == "soit.resources"
    )["value"]
    assert resumed_resources["responseId"] == resource_ids["response_id"]
    assert resumed_resources["executionRunId"] == resource_ids["run_id"]
    assert resumed_resources["taskId"] == resource_ids["task_id"]
    assert resumed_events[-1]["type"] == "RUN_FINISHED"
    assert resumed_events[-1]["result"]["status"] == "succeeded"
    assert response_service.get_interaction("interaction_approval_first").status == "succeeded"
    assert response_service.get_interaction("interaction_approval_resume").status == "succeeded"
    assert observe_service.approval_repo.get_by_id(resource_ids["approval_id"]).status == "approved"
    assert observe_service.approval_repo.get_by_id(decoy_approval.id).status == "pending"


def test_agui_approval_resume_rolls_back_when_child_enqueue_fails(
    client,
    db,
    ctx,
    monkeypatch,
):
    from app.kernel.runtime.tasks.service import TaskService
    from app.modules.observe.application.schemas import ApprovalCreate
    from app.modules.observe.application.service import ObserveService

    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}
    thread_response = client.post(
        "/api/v1/threads",
        json={"title": "Atomic approval resume"},
        headers=headers,
    )
    thread_id = thread_response.json()["data"]["id"]
    trace_writer = TraceWriter(db, ctx)
    task_service = TaskService(db, ctx)
    observe_service = ObserveService(db, ctx)
    response_service = ResponseService(
        db=db,
        ctx=ctx,
        response_repo=ResponseRepository(db, ctx),
        event_repo=ResponseEventRepository(db, ctx),
        trace_writer=trace_writer,
    )
    run = trace_writer.create_run(
        "agent",
        kind="agent",
        subject_kind="agent",
        subject_id="agent_atomic_resume",
    )
    trace_writer.update_run_status(run.id, "running")
    task = task_service.create_task(
        task_type="agent.stream",
        status="running",
        agent_id="agent_atomic_resume",
        thread_id=thread_id,
        run_id=run.id,
    )
    response = response_service.create_linked_response(
        run_id=run.id,
        thread_id=thread_id,
        task_id=task.id,
        agent_id="agent_atomic_resume",
        emit_initial_events=False,
    )
    response = response_service.mark_running(response)
    response_service.claim_interaction(
        interaction_id="interaction_atomic_parent",
        parent_interaction_id=None,
        thread_id=thread_id,
        request_hash="hash_atomic_parent",
    )
    response_service.create_interaction(
        interaction_id="interaction_atomic_parent",
        parent_interaction_id=None,
        response=response,
        request_hash="hash_atomic_parent",
    )
    response_service.update_interaction_status(
        "interaction_atomic_parent",
        "waiting_approval",
    )
    task_service.transition_task(task_id=task.id, status="waiting_approval")
    trace_writer.update_run_status(run.id, "waiting_approval")
    approval = asyncio.run(
        observe_service.create_approval(
            ApprovalCreate(
                run_id=run.id,
                task_id=task.id,
                thread_id=thread_id,
                agent_id="agent_atomic_resume",
                title="Atomic approval",
                details_json={"interrupt_id": "interrupt_atomic_resume"},
            )
        )
    )
    db.commit()

    original_claim = ResponseService.claim_interaction

    def fail_child_claim(self, **kwargs):
        if kwargs.get("interaction_id") == "interaction_atomic_child":
            raise RuntimeError("simulated child enqueue failure")
        return original_claim(self, **kwargs)

    monkeypatch.setattr(ResponseService, "claim_interaction", fail_child_claim)
    resume_payload = _agui_agent_run_input(
        thread_id=thread_id,
        run_id="interaction_atomic_child",
        agent_id="agent_atomic_resume",
        content="continue after approval",
    )
    resume_payload["parentRunId"] = "interaction_atomic_parent"
    resume_payload["resume"] = [
        {
            "interruptId": "interrupt_atomic_resume",
            "status": "resolved",
            "payload": {"decision": "approved"},
        }
    ]

    failed_response = client.post(
        "/api/v1/responses",
        json=resume_payload,
        headers=headers,
    )
    assert failed_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    db.expire_all()
    assert response_service.get_interaction("interaction_atomic_parent").status == "waiting_approval"
    assert response_service.get_interaction("interaction_atomic_child") is None
    assert observe_service.approval_repo.get_by_id(approval.id).status == "pending"


def test_responses_api_create_get_events_and_cancel(client):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}

    create_response = client.post(
        "/api/v1/responses",
        json={
            "model": "model:openai:gpt-5.1",
            "agent_id": "agent_test",
            "input": {
                "items": [
                    {"type": "input_text", "text": "hello"},
                ]
            },
            "metadata": {"source": "test"},
        },
        headers=headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    payload = create_response.json()["data"]
    assert payload["id"].startswith("resp_")
    assert payload["run_id"].startswith("run_")
    assert payload["status"] == "succeeded"
    assert payload["provider"] == "openai"
    assert payload["metadata_json"]["source"] == "test"
    assert payload["output_json"]["text"] == "hello"
    assert payload["usage_json"]["total_tokens"] >= 1

    response_id = payload["id"]

    get_response = client.get(f"/api/v1/responses/{response_id}", headers=headers)
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["data"]["id"] == response_id

    events_response = client.get(f"/api/v1/responses/{response_id}/events", headers=headers)
    assert events_response.status_code == status.HTTP_200_OK
    events_payload = events_response.json()["data"]
    assert len(events_payload["items"]) == 4
    assert events_payload["items"][0]["type"] == "response.created"
    assert events_payload["items"][1]["type"] == "response.input.added"
    assert events_payload["items"][2]["type"] == "response.output_text.done"
    assert events_payload["items"][3]["type"] == "response.succeeded"

    cancel_response = client.post(f"/api/v1/responses/{response_id}/cancel", headers=headers)
    assert cancel_response.status_code == status.HTTP_200_OK
    cancel_payload = cancel_response.json()["data"]
    assert cancel_payload["action"] == "cancel"
    assert cancel_payload["response"]["status"] == "succeeded"

    events_after_cancel = client.get(f"/api/v1/responses/{response_id}/events", headers=headers)
    assert events_after_cancel.status_code == status.HTTP_200_OK
    event_types = [item["type"] for item in events_after_cancel.json()["data"]["items"]]
    assert event_types == [
        "response.created",
        "response.input.added",
        "response.output_text.done",
        "response.succeeded",
    ]


def test_responses_api_rejects_removed_request_bound_stream_field(client):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}

    response = client.post(
        "/api/v1/responses",
        json={
            "model": "model:openai:gpt-5.1",
            "input": {"items": [{"type": "input_text", "text": "stream me"}]},
            "stream": True,
        },
        headers=headers,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["code"] == "VALIDATION_ERROR"
    errors = response.json()["details"]["errors"]
    assert any(error["field"].endswith("stream") for error in errors)


def test_responses_api_run_timeline(client):
    headers = {"X-Tenant-Id": "test-tenant", "X-Workspace-Id": "test-workspace"}

    create_response = client.post(
        "/api/v1/responses",
        json={
            "model": "model:openai:gpt-5.1",
            "input": {"items": [{"type": "input_text", "text": "timeline me"}]},
            "metadata": {"source": "timeline-test"},
        },
        headers=headers,
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    payload = create_response.json()["data"]

    timeline_response = client.get(
        f"/api/v1/responses/by-run/{payload['run_id']}",
        headers=headers,
    )
    assert timeline_response.status_code == status.HTTP_200_OK
    timeline_payload = timeline_response.json()["data"]
    assert timeline_payload["run_id"] == payload["run_id"]
    assert len(timeline_payload["items"]) == 1
    item = timeline_payload["items"][0]
    assert item["response"]["id"] == payload["id"]
    assert [event["type"] for event in item["events"]] == [
        "response.created",
        "response.input.added",
        "response.output_text.done",
        "response.succeeded",
    ]
