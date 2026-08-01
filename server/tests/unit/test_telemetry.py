"""Tests for real OpenTelemetry provider configuration."""

from unittest.mock import AsyncMock

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from app.infra.telemetry import build_tracer_provider
from app.kernel.contracts.context import RequestContext
from app.kernel.observe.tracing import OpenTelemetryTracer
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingResponse,
    GeneratedImage,
    ImageGenerationResponse,
    RerankResponse,
)
from app.kernel.ports.llm.policy import LLMPolicyGateway
from app.kernel.ports.tools.interface import ToolResponse
from app.kernel.ports.tools.policy import ToolPolicyGateway
from app.kernel.runtime.db.models.runs import Run, RunStep


def test_tracer_provider_exports_real_spans_with_service_resource() -> None:
    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(
        service_name="soit-test",
        exporter=exporter,
        batch=False,
    )

    with provider.get_tracer("test").start_as_current_span("unit-span"):
        pass

    spans = exporter.get_finished_spans()
    assert [span.name for span in spans] == ["unit-span"]
    assert spans[0].resource.attributes["service.name"] == "soit-test"


def test_execution_tracer_links_product_ids_to_spans() -> None:
    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(
        service_name="soit-test",
        exporter=exporter,
        batch=False,
    )
    execution_tracer = OpenTelemetryTracer(
        otel_tracer=provider.get_tracer("soit.execution"),
        emit=lambda _event, _payload: None,
    )
    run = Run(
        id="run-1",
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        mode="agent",
        kind="agent",
        status="running",
    )
    step = RunStep(
        id="step-1",
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        run_id=run.id,
        step_type="tool",
        status="succeeded",
    )

    execution_tracer.trace_run(run, {"event": "status"})
    execution_tracer.trace_step(step, {"event": "status"})

    spans = exporter.get_finished_spans()
    assert [span.name for span in spans] == ["soit.run.status", "soit.step.status"]
    assert spans[0].attributes["soit.run.id"] == "run-1"
    assert spans[0].attributes["soit.tenant.id"] == "tenant-1"
    assert spans[1].attributes["soit.run.id"] == "run-1"
    assert spans[1].attributes["soit.step.id"] == "step-1"


@pytest.mark.asyncio
async def test_llm_and_tool_gateways_emit_linked_dependency_spans() -> None:
    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(
        service_name="soit-test",
        exporter=exporter,
        batch=False,
    )
    ctx = RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        user_id="user-1",
    )
    llm_port = AsyncMock()
    llm_port.chat.return_value = ChatResponse(
        text="done",
        model="gpt-4",
        tokens_prompt=3,
        tokens_completion=5,
    )
    tool_port = AsyncMock()
    tool_port.invoke.return_value = ToolResponse(success=True, result={"ok": True})

    await LLMPolicyGateway(
        llm_port,
        ctx,
        max_retries=0,
        otel_tracer=provider.get_tracer("soit.llm"),
    ).chat([ChatMessage("user", "hello")], "model:openai:gpt-4", run_id="run-1")
    await ToolPolicyGateway(
        tool_port,
        ctx,
        max_retries=0,
        enable_egress_check=False,
        otel_tracer=provider.get_tracer("soit.tools"),
    ).invoke("tool:builtin:demo", {}, run_id="run-1")

    spans = exporter.get_finished_spans()
    assert [span.name for span in spans] == ["soit.llm.chat", "soit.tool.invoke"]
    assert spans[0].attributes["soit.run.id"] == "run-1"
    assert spans[0].attributes["gen_ai.usage.input_tokens"] == 3
    assert spans[1].attributes["soit.run.id"] == "run-1"
    assert spans[1].attributes["soit.tool.success"] is True


@pytest.mark.asyncio
async def test_image_generation_emits_a_linked_dependency_span() -> None:
    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(
        service_name="soit-test",
        exporter=exporter,
        batch=False,
    )
    ctx = RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        user_id="user-1",
    )
    llm_port = AsyncMock()
    llm_port.generate_image.return_value = ImageGenerationResponse(
        images=[GeneratedImage(b64_json="aW1n"), GeneratedImage(b64_json="aW1n")],
        model="seedream-4",
    )

    await LLMPolicyGateway(
        llm_port,
        ctx,
        max_retries=0,
        otel_tracer=provider.get_tracer("soit.llm"),
    ).generate_image(
        "a red dot",
        "model:volcengine:seedream-4",
        n=2,
        run_id="run-1",
    )

    spans = exporter.get_finished_spans()
    assert [span.name for span in spans] == ["soit.llm.generate_image"]
    attributes = spans[0].attributes
    assert attributes["soit.run.id"] == "run-1"
    assert attributes["soit.tenant.id"] == "tenant-1"
    assert attributes["gen_ai.operation.name"] == "image_generation"
    assert attributes["gen_ai.provider.name"] == "volcengine"
    assert attributes["gen_ai.response.model"] == "seedream-4"
    assert attributes["soit.llm.image.requested_count"] == 2
    assert attributes["soit.llm.image.generated_count"] == 2


class _StreamingLLMPort:
    """Minimal streaming port; AsyncMock cannot stand in for an async iterator."""

    async def stream_chat(self, **kwargs):
        del kwargs
        yield ChatStreamChunk(delta="he", model="gpt-4", tokens_prompt=3)
        yield ChatStreamChunk(delta="llo", model="gpt-4", tokens_completion=5, done=True)


@pytest.mark.asyncio
async def test_stream_embed_and_rerank_emit_linked_dependency_spans() -> None:
    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(
        service_name="soit-test",
        exporter=exporter,
        batch=False,
    )
    ctx = RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        user_id="user-1",
    )

    stream_gateway = LLMPolicyGateway(
        _StreamingLLMPort(),
        ctx,
        max_retries=0,
        otel_tracer=provider.get_tracer("soit.llm"),
    )
    chunks = [
        chunk
        async for chunk in stream_gateway.stream_chat(
            [ChatMessage("user", "hello")],
            "model:openai:gpt-4",
            run_id="run-1",
        )
    ]
    assert [chunk.delta for chunk in chunks] == ["he", "llo"]

    llm_port = AsyncMock()
    llm_port.embed.return_value = EmbeddingResponse(
        embeddings=[[0.1, 0.2]],
        tokens_used=7,
        model="text-embedding-3-small",
    )
    llm_port.rerank.return_value = RerankResponse(
        results=[{"index": 0, "score": 0.9}],
        tokens_used=11,
        model="rerank-v1",
    )
    gateway = LLMPolicyGateway(
        llm_port,
        ctx,
        max_retries=0,
        otel_tracer=provider.get_tracer("soit.llm"),
    )
    await gateway.embed(
        ["first", "second"],
        "model:openai:text-embedding-3-small",
        run_id="run-1",
    )
    await gateway.rerank(
        "query",
        ["doc-1", "doc-2", "doc-3"],
        "model:cohere:rerank-v1",
        top_n=2,
        run_id="run-1",
    )

    spans = exporter.get_finished_spans()
    assert [span.name for span in spans] == [
        "soit.llm.stream_chat",
        "soit.llm.embed",
        "soit.llm.rerank",
    ]
    stream_span, embed_span, rerank_span = spans
    assert stream_span.attributes["soit.run.id"] == "run-1"
    assert stream_span.attributes["soit.llm.streaming"] is True
    assert stream_span.attributes["gen_ai.response.model"] == "gpt-4"
    assert stream_span.attributes["gen_ai.usage.input_tokens"] == 3
    assert stream_span.attributes["gen_ai.usage.output_tokens"] == 5
    assert embed_span.attributes["gen_ai.operation.name"] == "embeddings"
    assert embed_span.attributes["soit.llm.embed.input_count"] == 2
    assert embed_span.attributes["gen_ai.usage.input_tokens"] == 7
    assert rerank_span.attributes["gen_ai.operation.name"] == "rerank"
    assert rerank_span.attributes["gen_ai.provider.name"] == "cohere"
    assert rerank_span.attributes["soit.llm.rerank.document_count"] == 3
    assert rerank_span.attributes["soit.llm.rerank.top_n"] == 2
    assert rerank_span.attributes["gen_ai.usage.input_tokens"] == 11


@pytest.mark.asyncio
async def test_failed_stream_marks_its_span_as_an_error() -> None:
    exporter = InMemorySpanExporter()
    provider = build_tracer_provider(
        service_name="soit-test",
        exporter=exporter,
        batch=False,
    )
    ctx = RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        user_id="user-1",
    )

    class _FailingStreamPort:
        async def stream_chat(self, **kwargs):
            del kwargs
            raise RuntimeError("upstream is unavailable")
            yield  # pragma: no cover - makes this an async generator

    gateway = LLMPolicyGateway(
        _FailingStreamPort(),
        ctx,
        max_retries=0,
        otel_tracer=provider.get_tracer("soit.llm"),
    )
    with pytest.raises(RuntimeError):
        async for _ in gateway.stream_chat(
            [ChatMessage("user", "hello")],
            "model:openai:gpt-4",
            run_id="run-1",
        ):
            pass

    spans = exporter.get_finished_spans()
    assert [span.name for span in spans] == ["soit.llm.stream_chat"]
    assert spans[0].status.status_code.name == "ERROR"
