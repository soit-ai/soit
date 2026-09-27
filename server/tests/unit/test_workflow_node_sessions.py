"""Workflow nodes run on their own sessions when the context can build them.

A session cannot be driven from two tasks at once, so without a node context
factory the executor runs nodes one at a time on the shared session. With one,
every node gets a context of its own and the executor commits and closes that
context's session when the node is done. Real overlap needs row-level locking,
so that half of the contract lives in ``tests/postgres``.

A workflow an agent starts through its bindings is held to the same contract:
its concurrent nodes query knowledge through ports built on their own node
sessions, never through the agent's.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.ports.llm.interface import ChatResponse, LLMPort, ToolCall
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.agent.application.schemas import (
    AgentCreate,
    AgentRunRequest,
    AgentVersionCreate,
)
from app.modules.workflow.application.schemas import (
    WorkflowCreate,
    WorkflowVersionCreate,
)
from app.modules.workflow.application.service import WorkflowService
from app.modules.workflow.runtime.engine import ExecutionEngine
from app.modules.workflow.runtime.executor import WorkflowExecutor
from app.modules.workflow.runtime.executors.base import ExecutionContext
from app.wiring.services import build_agent_service
from app.wiring.workflow_resources import KnowledgeRuntimeWorkflowQueryAdapter


class OverlapRecordingToolPort(ToolPort):
    """Tool port that measures how many invocations were in flight at once."""

    def __init__(self) -> None:
        self.active = 0
        self.peak = 0
        self.calls: list[str] = []

    async def invoke(self, tool_ref: str, parameters: dict[str, Any], **kwargs: Any) -> ToolResponse:
        self.active += 1
        self.peak = max(self.peak, self.active)
        self.calls.append(tool_ref)
        try:
            await asyncio.sleep(0.05)
        finally:
            self.active -= 1
        return ToolResponse(result={"tool_ref": tool_ref}, success=True, metadata={})


class _SessionSpy:
    """Stands in for a node's owned session; the real writes go elsewhere."""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def close(self) -> None:
        self.closed = True


def fan_out_plan(run_id: str, *, concurrency: int = 2) -> ExecutionPlan:
    return ExecutionPlan(
        run_id=run_id,
        mode="workflow",
        inputs={},
        plan_data={
            "nodes": {
                "left": {"id": "left", "type": "tool", "input": {"tool_ref": "tool:function:left"}},
                "right": {"id": "right", "type": "tool", "input": {"tool_ref": "tool:function:right"}},
                "join": {
                    "id": "join",
                    "type": "output",
                    "input": {"value": "{{ steps.left.output.result.tool_ref }}+{{ steps.right.output.result.tool_ref }}"},
                },
            },
            "edges": [{"from": "left", "to": "join"}, {"from": "right", "to": "join"}],
            "execution_order": ["left", "right", "join"],
            "semantics": {"concurrency": concurrency},
            "policy": {},
        },
    )


@pytest.mark.asyncio
async def test_without_a_factory_nodes_run_one_at_a_time(async_db, ctx: RequestContext) -> None:
    trace_writer = TraceWriter(async_db, ctx)
    run = await trace_writer.create_run(mode="workflow", kind="workflow")
    tool_port = OverlapRecordingToolPort()
    context = ExecutionContext(
        run_id=run.id, step_id=None, ctx=ctx, trace_writer=trace_writer, tool_port=tool_port, workflow_policy={}
    )

    output = await WorkflowExecutor(ExecutionEngine(async_db, ctx, trace_writer)).execute(
        fan_out_plan(run.id), context
    )

    assert output["value"] == "tool:function:left+tool:function:right"
    assert tool_port.peak == 1


@pytest.mark.asyncio
async def test_every_node_gets_its_own_context_which_is_committed_and_closed(
    async_db, ctx: RequestContext
) -> None:
    """The in-memory database has one connection, so the node contexts here
    write through the shared session and only the ownership bookkeeping is
    exercised: one context per node, each committed and closed exactly once."""
    trace_writer = TraceWriter(async_db, ctx)
    run = await trace_writer.create_run(mode="workflow", kind="workflow")
    tool_port = OverlapRecordingToolPort()
    spies: list[_SessionSpy] = []

    async def build_node_context() -> ExecutionContext:
        spy = _SessionSpy()
        spies.append(spy)
        return ExecutionContext(
            run_id=run.id,
            step_id=None,
            ctx=ctx,
            trace_writer=trace_writer,
            tool_port=tool_port,
            workflow_policy={},
            owned_session=spy,  # type: ignore[arg-type]
        )

    context = ExecutionContext(
        run_id=run.id,
        step_id=None,
        ctx=ctx,
        trace_writer=trace_writer,
        tool_port=tool_port,
        workflow_policy={},
        node_context_factory=build_node_context,
    )
    # A chain rather than a fan-out: the shared session must not be driven
    # from two tasks, and this test is about ownership, not overlap.
    plan = fan_out_plan(run.id)
    plan.plan_data["edges"] = [{"from": "left", "to": "right"}, {"from": "right", "to": "join"}]

    output = await WorkflowExecutor(ExecutionEngine(async_db, ctx, trace_writer)).execute(plan, context)

    assert output["value"] == "tool:function:left+tool:function:right"
    assert len(spies) == 3
    assert all(spy.commits == 1 and spy.closed for spy in spies)
    assert all(spy.rollbacks == 0 for spy in spies)


class _RecordingSession:
    """Delegates to the shared session and remembers what was staged through it."""

    def __init__(self, inner) -> None:
        self._inner = inner
        self.staged: list[object] = []

    def add(self, instance, *args, **kwargs):
        self.staged.append(instance)
        return self._inner.add(instance, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._inner, name)


@pytest.mark.asyncio
async def test_node_completion_is_staged_on_the_node_session(async_db, ctx: RequestContext) -> None:
    """The node's outbox row and checkpoint go through its own session.

    Staging them on the shared context let two branches finishing together
    drive one session from two tasks, which PostgreSQL showed as an
    intermittent IllegalStateChangeError and serialized branches.
    """
    from app.kernel.runtime.db.models.events import EventOutbox
    from app.modules.workflow.domain.models import Workflow, WorkflowRun

    trace_writer = TraceWriter(async_db, ctx)
    run = await trace_writer.create_run(mode="workflow", kind="workflow")
    workflow = Workflow(tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, name="node-session-outbox")
    async_db.add(workflow)
    await async_db.flush()
    workflow_run = WorkflowRun(
        tenant_id=ctx.tenant_id, workspace_id=ctx.workspace_id, run_id=run.id,
        workflow_id=workflow.id, status="running", total_nodes=3,
    )
    async_db.add(workflow_run)
    await async_db.commit()

    node_sessions: list[_RecordingSession] = []

    async def build_node_context() -> ExecutionContext:
        recording = _RecordingSession(async_db)
        node_sessions.append(recording)
        return ExecutionContext(
            run_id=run.id, step_id=None, ctx=ctx,
            trace_writer=TraceWriter(recording, ctx),  # type: ignore[arg-type]
            tool_port=OverlapRecordingToolPort(), workflow_policy={},
            workflow_run_id=workflow_run.id,
            owned_session=_SessionSpy(),  # type: ignore[arg-type]
        )

    shared = _RecordingSession(async_db)
    context = ExecutionContext(
        run_id=run.id, step_id=None, ctx=ctx,
        trace_writer=TraceWriter(shared, ctx),  # type: ignore[arg-type]
        tool_port=OverlapRecordingToolPort(), workflow_policy={},
        workflow_run_id=workflow_run.id, node_context_factory=build_node_context,
    )
    plan = fan_out_plan(run.id)
    plan.plan_data["edges"] = [{"from": "left", "to": "right"}, {"from": "right", "to": "join"}]

    await WorkflowExecutor(ExecutionEngine(async_db, ctx, trace_writer)).execute(plan, context)

    def outbox_rows(session: _RecordingSession) -> list[EventOutbox]:
        return [item for item in session.staged if isinstance(item, EventOutbox) and item.event_type == "workflow.node.completed"]

    assert len(node_sessions) == 3
    assert all(len(outbox_rows(session)) == 1 for session in node_sessions)
    assert outbox_rows(shared) == []


class _QueueLLMPort(LLMPort):
    def __init__(self, responses: list[ChatResponse]) -> None:
        self._responses = list(responses)

    async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
        return self._responses.pop(0)

    async def embed(self, texts, model, **kwargs):
        raise NotImplementedError

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        raise NotImplementedError


class _KnowledgeQueries:
    """The session each knowledge query's port was built on, and how many overlapped."""

    def __init__(self) -> None:
        self.sessions: dict[str, object] = {}
        self.active = 0
        self.peak = 0


class _RecordingKnowledgePort:
    def __init__(self, queries: _KnowledgeQueries, session: object) -> None:
        self._queries = queries
        self._session = session

    async def query(self, *, knowledge_ref: str, **kwargs: Any) -> dict[str, Any]:
        self._queries.sessions[knowledge_ref] = self._session
        self._queries.active += 1
        self._queries.peak = max(self._queries.peak, self._queries.active)
        try:
            await asyncio.sleep(0.05)
        finally:
            self._queries.active -= 1
        return {"context": knowledge_ref.removeprefix("knowledge:"), "citations": []}


@pytest.mark.asyncio
async def test_a_workflow_an_agent_starts_queries_knowledge_on_each_node_session(
    async_db, ctx: RequestContext
) -> None:
    """Two retrieve nodes of an agent-bound workflow run at once, each through
    a knowledge port on its own node session. Handing both the agent's port
    drove the agent's session from two tasks, and one query settling its run
    could commit or roll back what the other node and the agent had staged."""
    workflows = WorkflowService(db=async_db, ctx=ctx)
    workflow = await workflows.create_workflow(WorkflowCreate(name="agent-fan-out-retrieval"))
    retrieve = {"query": "{{ inputs.question }}", "top_k": 3}
    version = await workflows.create_version(
        workflow.id,
        WorkflowVersionCreate(
            graph_json={
                "name": "agent-fan-out-retrieval",
                "inputs_schema": {"type": "object", "properties": {"question": {"type": "string"}}},
                "outputs_schema": {"type": "object", "properties": {"value": {}}},
                "semantics": {"concurrency": 2},
                "graph": {
                    "nodes": [
                        {"id": "policy", "type": "retrieve", "params": {**retrieve, "knowledge_ref": "knowledge:policy"}},
                        {"id": "faq", "type": "retrieve", "params": {**retrieve, "knowledge_ref": "knowledge:faq"}},
                        {
                            "id": "output",
                            "type": "output",
                            "params": {"value": "{{ steps.policy.output.context }}+{{ steps.faq.output.context }}"},
                        },
                    ],
                    "edges": [
                        {"id": "edge-policy-output", "from": "policy", "to": "output"},
                        {"id": "edge-faq-output", "from": "faq", "to": "output"},
                    ],
                },
            }
        ),
    )
    await workflows.publish_version(workflow.id, version.id)
    workflow_ref = f"wf:{workflow.id}"

    shared = _KnowledgeQueries()
    per_node = _KnowledgeQueries()
    agents = AgentApplicationService(
        db=async_db,
        ctx=ctx,
        llm_port=_QueueLLMPort(
            [
                ChatResponse(
                    text=None,
                    finish_reason="tool_calls",
                    tool_calls=[ToolCall(id="call_fan_out", name=workflow_ref, arguments={"question": "Refund?"})],
                ),
                ChatResponse(text="Both sources agree.", finish_reason="stop"),
            ]
        ),
        tool_port=OverlapRecordingToolPort(),
        workflow_knowledge_query_port=_RecordingKnowledgePort(shared, async_db),
        node_knowledge_query_port_factory=lambda session: _RecordingKnowledgePort(per_node, session),
    )
    agent = await agents.create_agent(AgentCreate(name="fan-out-agent", visibility="private"))
    agent_version = await agents.create_version(
        agent.id,
        AgentVersionCreate(
            system_prompt="Answer from the bound workflow.",
            bindings={"model_ref": "model:test:primary", "workflow_refs": [workflow_ref]},
            verify=False,
        ),
    )
    await agents.publish_version(agent.id, agent_version.id)

    result = await agents.execute_agent(
        agent.id, AgentRunRequest(input="Can I get a refund?").model_dump(exclude_none=True)
    )

    _, _, tool_calls = await agents.response_service.get_response_detail(result["response_id"])
    workflow_call = next(call for call in tool_calls if call["tool_name"] == workflow_ref)
    assert workflow_call["result_json"]["result"]["output"] == {"value": "policy+faq"}
    assert result["output"] == "Both sources agree."
    assert shared.sessions == {}, "a node queried through the agent's knowledge port"
    assert set(per_node.sessions) == {"knowledge:policy", "knowledge:faq"}
    assert per_node.sessions["knowledge:policy"] is not per_node.sessions["knowledge:faq"]
    assert all(session is not async_db for session in per_node.sessions.values())
    assert per_node.peak == 2, "the two retrieve nodes did not overlap"


@pytest.mark.asyncio
async def test_the_wired_agent_service_builds_a_knowledge_port_on_the_node_session(
    async_db, ctx: RequestContext
) -> None:
    """The factory the test above injects by hand is the one production wires in."""
    service = build_agent_service(db=async_db, ctx=ctx)
    node_session = AsyncSession(bind=async_db.bind, expire_on_commit=False)
    try:
        assert service.node_knowledge_query_port_factory is not None
        port = service.node_knowledge_query_port_factory(node_session)
        assert isinstance(port, KnowledgeRuntimeWorkflowQueryAdapter)
        assert port._runtime_service.db is node_session
    finally:
        await node_session.close()
