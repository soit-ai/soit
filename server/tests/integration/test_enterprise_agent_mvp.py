"""Enterprise agent MVP golden-path integration test."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import and_, select

from app.adapters.secrets.memory import InMemorySecretsPort
from app.adapters.tools.router import RegistryToolRouterPort
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import (
    ChatResponse,
    EmbeddingResponse,
    LLMPort,
    RerankResponse,
    ToolCall,
)
from app.kernel.runtime.db.models.runs import Run, RunCostEntry, RunStep
from app.kernel.runtime.responses.repository import ResponseEventRepository
from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.agent.application.schemas import (
    AgentCreate,
    AgentRunRequest,
    AgentVersionCreate,
    ChatMessageInput,
)
from app.modules.knowledge.application.runtime_schemas import (
    DocumentUpload,
    KnowledgeCreate,
    QueryRequest,
)
from app.modules.knowledge.domain.models import KnowledgeIndex
from app.modules.modelhub.application.schemas import ProviderCreate, ProviderModelCreate
from app.modules.modelhub.application.service import ModelHubService
from app.modules.modelhub.domain.models import ProviderModel
from app.modules.modelhub.infra.providers import ProviderCatalogAdapter
from app.modules.modelhub.infra.repository import (
    PlatformModelRepository,
    ProviderModelRepository,
    ProviderRepository,
    SyncJobRepository,
)
from app.modules.workflow.application.service import WorkflowService
from app.modules.workflow.domain.models import WorkflowRun
from app.wiring.container import reset_container
from app.wiring.services import build_knowledge_runtime_service


class QueueLLMPort(LLMPort):
    """LLM stub returning queued chat responses."""

    def __init__(self, responses: list[ChatResponse]) -> None:
        self._responses = list(responses)

    async def chat(self, messages, model, temperature=None, max_tokens=None, *, tools=None, tool_choice=None, **kwargs):
        if not self._responses:
            raise AssertionError("QueueLLMPort has no queued chat response")
        return self._responses.pop(0)

    async def embed(self, texts, model, **kwargs):
        return EmbeddingResponse(embeddings=[[0.0, 0.0, 0.0] for _ in texts], tokens_used=len(texts), model=model)

    async def rerank(self, query, documents, model, top_n=None, **kwargs):
        return RerankResponse(
            results=[{"index": idx, "document": doc, "score": 1.0} for idx, doc in enumerate(documents[: top_n or None])],
            tokens_used=0,
            model=model,
        )


class StubMemoryService:
    """Memory stub returning no enterprise memories."""

    async def query_memory(self, data, run_id=None):
        return [SimpleNamespace(memory=SimpleNamespace(content_summary="enterprise mvp", content={}), score=0.1)]


def _unwrap(row: Any) -> Any:
    if row is None:
        return None
    if isinstance(row, tuple):
        return row[0]
    try:
        return row[0]
    except Exception:
        return row


@pytest.mark.asyncio
async def test_enterprise_agent_mvp_publishes_and_executes_with_knowledge_workflow_tool_and_trace(
    db,
    tenant1_ctx: RequestContext,
    monkeypatch,
):
    reset_container()
    try:
        knowledge_service = build_knowledge_runtime_service(db=db, ctx=tenant1_ctx)
        modelhub_service = ModelHubService(
            db=db,
            ctx=tenant1_ctx,
            provider_repo=ProviderRepository(db, tenant1_ctx),
            platform_model_repo=PlatformModelRepository(db, tenant1_ctx),
            provider_model_repo=ProviderModelRepository(db, tenant1_ctx),
            sync_job_repo=SyncJobRepository(db, tenant1_ctx),
            secrets_port=InMemorySecretsPort(),
            catalog_adapter=ProviderCatalogAdapter(),
        )
        provider = await modelhub_service.create_provider(
            ProviderCreate(
                kind="test",
                slug="chain-a-test",
                name="Chain A Test Provider",
                status="active",
                runtime_config_json={"adapter": "memory"},
            )
        )
        provider_model = await modelhub_service.create_provider_model(
            provider.id,
            ProviderModelCreate(
                model_id="chain-a-agent",
                display_name="Chain A Agent Model",
                capabilities_json={"chat": True, "tool_calling": True},
                status="active",
            ),
        )
        model_ref = f"model:{provider_model.provider_kind}:{provider_model.model_id}"

        knowledge = await knowledge_service.create_knowledge(
            KnowledgeCreate(
                name="enterprise_support_kb",
                type="document",
                description="Enterprise support policies",
                default_embedding_model_ref="model:test:embedding",
            )
        )
        document = await knowledge_service.upload_document(
            knowledge.id,
            DocumentUpload(
                doc_key="refund-policy.md",
                source_kind="upload",
                title="Refund Policy",
                source_uri="kb://refund-policy.md",
            ),
            file_content=b"Refund escalations require account verification before a review ticket is created.",
        )
        index = _unwrap(
            db.exec(
                select(KnowledgeIndex).where(
                    and_(
                        KnowledgeIndex.tenant_id == tenant1_ctx.tenant_id,
                        KnowledgeIndex.workspace_id == tenant1_ctx.workspace_id,
                        KnowledgeIndex.knowledge_id == knowledge.id,
                        KnowledgeIndex.status == "ready",
                    )
                )
            ).first()
        )
        assert document.status == "indexed"
        assert index is not None
        collection_name = index.collection_name or f"idx_{index.id}"

        async def query_test_knowledge(**kwargs):
            response = await knowledge_service.query(
                kwargs["knowledge_id"],
                QueryRequest(
                    query=kwargs["query"],
                    top_k=kwargs.get("top_k", 5),
                    index_id=kwargs.get("index_id"),
                    filter=kwargs.get("filter"),
                    include_snippets=kwargs.get("include_snippets", True),
                    strategy=kwargs.get("strategy"),
                ),
            )
            return response.model_dump()

        monkeypatch.setattr("app.modules.knowledge.application.tools.knowledge_query", query_test_knowledge)

        workflow_service = WorkflowService(db=db, ctx=tenant1_ctx)
        workflow = await workflow_service.create_ticket_triage_template(name="Enterprise ticket triage")
        assert workflow.current_version_id is not None
        workflow = await workflow_service.publish_version(workflow.id, workflow.current_version_id)
        workflow_ref = f"wf:{workflow.id}"

        agent_llm = QueueLLMPort(
            [
                ChatResponse(
                    text=None,
                    tokens_prompt=11,
                    tokens_completion=3,
                    model="test-agent",
                    finish_reason="tool_calls",
                    tool_calls=[
                        ToolCall(
                            id="call_ticket_workflow",
                            name=workflow_ref,
                            arguments={
                                "customer_message": "Customer requests a refund escalation.",
                                "customer_id": "customer-123",
                                "priority": "high",
                                "knowledge_collection": collection_name,
                                "embedding_model": "model:test:embedding",
                                "model_ref": "model:test:workflow",
                            },
                        )
                    ],
                ),
                ChatResponse(
                    text="A review ticket was created after checking the refund policy.",
                    tokens_prompt=17,
                    tokens_completion=10,
                    model="test-agent",
                    finish_reason="stop",
                ),
            ]
        )
        agent_service = AgentApplicationService(
            db=db,
            ctx=tenant1_ctx,
            llm_port=agent_llm,
            tool_port=RegistryToolRouterPort(),
            memory_service=StubMemoryService(),
        )
        agent = await agent_service.create_agent(
            AgentCreate(
                name="enterprise-mvp-agent",
                description="Enterprise MVP golden path",
                visibility="private",
                tags=["enterprise", "mvp"],
            )
        )
        active_provider_model = _unwrap(
            db.exec(
                select(ProviderModel).where(
                    and_(
                        ProviderModel.tenant_id == tenant1_ctx.tenant_id,
                        ProviderModel.workspace_id == tenant1_ctx.workspace_id,
                        ProviderModel.provider_id == provider.id,
                        ProviderModel.model_id == "chain-a-agent",
                        ProviderModel.status == "active",
                    )
                )
            ).first()
        )
        version = await agent_service.create_version(
            agent.id,
            AgentVersionCreate(
                system_prompt="Use enterprise knowledge and ticket workflows.",
                temperature=0.1,
                bindings={
                    "model_ref": model_ref,
                    "knowledge_refs": [f"knowledge:{knowledge.id}"],
                    "tool_refs": ["builtin.ticket.create_review_ticket"],
                    "workflow_refs": [workflow_ref],
                },
                memory_strategy="planner_only",
                memory_top_k=1,
                verify=False,
            ),
        )
        await agent_service.publish_version(agent.id, version.id)
        assert active_provider_model is not None
        assert version.spec_json["bindings"]["model_ref"] == model_ref

        result = await agent_service.execute_agent(
            agent.id,
            AgentRunRequest(
                messages=[ChatMessageInput(role="user", content="Create a review ticket for this refund escalation.")],
                rag_top_k=3,
                max_iterations=4,
                verify=False,
            ).model_dump(exclude_none=True),
        )

        response, _, agent_tool_calls = agent_service.response_service.get_response_detail(result["response_id"])
        workflow_tool_call = next(call for call in agent_tool_calls if call["tool_name"] == workflow_ref)
        workflow_run_id = workflow_tool_call["result_json"]["result"]["workflow_run_id"]

        workflow_run = _unwrap(db.exec(select(WorkflowRun).where(WorkflowRun.run_id == workflow_run_id)).first())
        workflow_trace = _unwrap(db.exec(select(Run).where(Run.id == workflow_run_id)).first())
        agent_trace = _unwrap(db.exec(select(Run).where(Run.id == result["run_id"])).first())
        workflow_steps = list(db.exec(select(RunStep).where(RunStep.run_id == workflow_run_id)).all())
        tool_steps = [
            _unwrap(step)
            for step in workflow_steps
            if (_unwrap(step).metrics_json or {}).get("tool_call", {}).get("tool_ref")
            == "builtin.ticket.create_review_ticket"
        ]
        completed_tool_steps = [
            step
            for step in tool_steps
            if step.status == "succeeded"
            and (step.metrics_json or {}).get("tool_call", {}).get("status") == "completed"
        ]
        cost_entries = list(
            db.exec(
                select(RunCostEntry).where(
                    and_(
                        RunCostEntry.tenant_id == tenant1_ctx.tenant_id,
                        RunCostEntry.workspace_id == tenant1_ctx.workspace_id,
                        RunCostEntry.run_id.in_([result["run_id"], workflow_run_id]),
                    )
                )
            ).all()
        )
        response_events = ResponseEventRepository(db, tenant1_ctx).list_for_response(
            result["response_id"],
            limit=50,
            offset=0,
        )

        assert result["output"]
        assert result["model"] == model_ref
        assert result["citations"]
        assert result["citations"][0]["document_id"] == document.id
        assert response.output_json["citations"] == result["citations"]
        assert workflow_tool_call["status"] == "completed"
        assert workflow_run is not None
        assert workflow_run.workflow_id == workflow.id
        assert workflow_run.status == "succeeded"
        assert workflow_trace is not None
        assert workflow_trace.subject_kind == "workflow"
        assert workflow_trace.subject_id == workflow.id
        assert agent_trace is not None
        assert agent_trace.subject_kind == "agent"
        assert completed_tool_steps, [
            {
                "id": step.id,
                "type": step.step_type,
                "node_id": step.node_id,
                "status": step.status,
                "error": step.error_message,
                "tool_call": (step.metrics_json or {}).get("tool_call"),
            }
            for step in tool_steps
        ]
        assert any(_unwrap(entry).unit == "tokens" for entry in cost_entries)
        assert any(_unwrap(entry).unit == "requests" and _unwrap(entry).tool_ref == "builtin.ticket.create_review_ticket" for entry in cost_entries)
        assert any(event.type == "tool.call.completed" and event.payload_json.get("tool_type") == "workflow" for event in response_events)
    finally:
        reset_container()
