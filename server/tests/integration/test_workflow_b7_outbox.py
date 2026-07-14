"""B7: workflow execution emits node outbox rows; dispatcher updates workflow_runs (engine path)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, select

from app.kernel.contracts.context import RequestContext
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.events.dispatcher import OutboxDispatcher
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    LLMPort,
    RerankResponse,
)
from app.kernel.ports.tools.interface import ToolPort, ToolResponse
from app.kernel.runtime.db.models.events import EventOutbox
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.workflow.domain.models import Workflow, WorkflowRun
from app.modules.workflow.runtime.engine import ExecutionEngine
from app.wiring.outbox_handlers import get_outbox_registry, register_outbox_handlers


class _FakeLLMPort(LLMPort):
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        return ChatResponse(text="ok", model=model, finish_reason="stop")

    async def embed(self, texts: list[str], model: str, **kwargs: Any) -> EmbeddingResponse:
        return EmbeddingResponse(embeddings=[[0.0] * 3 for _ in texts], tokens_used=0, model=model)

    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str,
        top_n: int | None = None,
        **kwargs: Any,
    ) -> RerankResponse:
        return RerankResponse(results=[], tokens_used=0, model=model)


class _FakeToolPort(ToolPort):
    async def invoke(self, tool_ref: str, parameters: dict[str, Any], **kwargs: Any) -> ToolResponse:
        return ToolResponse(result={}, success=True, metadata={})


def _patched_container() -> MagicMock:
    c = MagicMock()
    c.get_llm_port = lambda ctx, trace_writer: _FakeLLMPort()
    c.get_tool_port = lambda ctx, trace_writer: _FakeToolPort()
    c.get_vector_port = lambda ctx, trace_writer: None
    c.get_plugin_runtime_port = lambda ctx, trace_writer: None
    return c


@pytest.mark.asyncio
@patch("app.wiring.get_container")
async def test_b7_workflow_engine_emits_node_outbox_and_projection(
    mock_get_container: MagicMock,
    db: Session,
    ctx: RequestContext,
) -> None:
    mock_get_container.return_value = _patched_container()
    register_outbox_handlers()
    reg = get_outbox_registry()

    trace_writer = TraceWriter(db, ctx)
    engine = ExecutionEngine(db, ctx, trace_writer, response_service=None)
    workflow = Workflow(
        id="wf-b7-outbox",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name="workflow-b7-outbox",
    )
    db.add(workflow)
    db.commit()

    plan = ExecutionPlan(
        mode="workflow",
        subject_kind="workflow",
        subject_id=workflow.id,
        subject_version_id="ver-b7",
        inputs={},
        plan_data={
            "nodes": {
                "a": {"id": "a", "type": "set_var", "input": {"set": {"x": 42}}},
                "b": {"id": "b", "type": "output", "input": {"value": "{{ steps.a.output.x }}"}},
            },
            "edges": [{"from": "a", "to": "b"}],
            "execution_order": ["a", "b"],
            "semantics": {"concurrency": 1},
            "policy": {},
        },
    )

    result = await engine.execute(plan)
    assert result.get("value") == 42

    wfr = db.exec(select(WorkflowRun).where(WorkflowRun.run_id == plan.run_id)).first()
    assert wfr is not None
    assert wfr.status == "succeeded"
    assert wfr.workflow_id == workflow.id

    pending = list(
        db.exec(
            select(EventOutbox).where(
                EventOutbox.workflow_run_id == wfr.id,
                EventOutbox.event_type == "workflow.node.completed",
            )
        ).all()
    )
    assert len(pending) >= 2

    dispatcher = OutboxDispatcher(db, reg)
    for _ in range(20):
        n = await dispatcher.run_once(batch_limit=40)
        db.commit()
        if n == 0:
            break

    db.refresh(wfr)
    assert wfr.completed_nodes == 2
    assert wfr.waiting_nodes == 0

    all_wf = list(db.exec(select(EventOutbox).where(EventOutbox.workflow_run_id == wfr.id)).all())
    for ob in all_wf:
        refreshed = db.get(EventOutbox, ob.id)
        assert refreshed is not None
        assert refreshed.status == "done"
